import csv
from dataclasses import replace
import importlib.util
import json
from math import dist
from pathlib import Path
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from config import DEFAULT_CONFIG as C
from contracts import HandSample, RobotCommand, SimStatus, ControllerState as State
from control import Controller, extract_hand_features
from dev.hand_samples import make_sample
from metrics import Metrics
from simulation import Simulation
from simulation.serve import IntegrationBridge
from vision import sample_from_landmarks, match_hand_to_arm


class VisionGeometryTests(unittest.TestCase):
    @staticmethod
    def arm(points):
        wrist = points[0] if points else (.5, .7, 0)
        return {"shoulder": (.5, .2, 0, 1, 1), "elbow": (.5, .4, 0, 1, 1),
                "wrist": (*wrist, 1, 1)}

    def test_pixel_aspect_ratio_and_palm_center(self):
        points = [(.5, .5, 0)] * 21
        points[0] = (.5, .7, 0)
        points[4], points[8] = (.4, .5, 0), (.45, .5, 0)
        sample = sample_from_landmarks(points, self.arm(points), 640, 480, 1, 1, 1.01)
        self.assertTrue(sample.valid)
        features = extract_hand_features(sample)
        self.assertAlmostEqual(features.pinch_ratio, 32 / 96)
        self.assertAlmostEqual(features.u, .5)
        self.assertAlmostEqual(features.v, .54)

    def test_missing_tiny_or_nonfinite_hand_is_invalid(self):
        for points in ([], [(.5, .5, 0)] * 21, [(float("nan"), .5, 0)] * 21):
            self.assertIsNone(extract_hand_features(sample_from_landmarks(points, self.arm(points), 640, 480, 1, 1, 1)))

    def test_partial_or_malformed_landmarks_do_not_control_robot(self):
        points = [(.5, .5, 0)] * 21
        points[0] = (.5, .7, 0)
        for invalid_tip in ((1.2, .5, 0), (.5, -.1, 0), (.5, .5, float("nan")), (.5,)):
            points[8] = invalid_tip
            self.assertIsNone(extract_hand_features(sample_from_landmarks(points, self.arm(points), 640, 480, 1, 1, 1)))

    def test_raw_contract_distinguishes_missing_pose_hand_and_pairing(self):
        sample = make_sample(1, 1, 1)
        args = (640, 480, 1, 1, 1)
        no_pose = sample_from_landmarks(sample.hand_keypoints, {}, *args)
        self.assertFalse(no_pose.valid)
        self.assertTrue(no_pose.hand_valid)
        self.assertFalse(no_pose.pose_valid)
        no_hand = sample_from_landmarks([], sample.arm_keypoints, *args)
        self.assertFalse(no_hand.valid)
        self.assertTrue(no_hand.pose_valid)
        self.assertFalse(no_hand.hand_valid)
        arm = dict(sample.arm_keypoints, wrist=(.1, .1, 0, 1, 1))
        mismatched = sample_from_landmarks(sample.hand_keypoints, arm, *args)
        self.assertFalse(mismatched.valid)
        self.assertTrue(mismatched.pose_valid and mismatched.hand_valid)

    def test_selected_hand_missing_never_falls_back_to_other_arm(self):
        from types import SimpleNamespace as NS
        sample = make_sample(1, 1, 1)
        other_hand = [NS(x=.05, y=.05, z=0)] * 21
        self.assertEqual(match_hand_to_arm([other_hand], sample.arm_keypoints, 640, 480), [])
        selected_hand = [NS(x=x, y=y, z=z) for x, y, z in sample.hand_keypoints]
        self.assertEqual(match_hand_to_arm([selected_hand], {}, 640, 480), [])
        self.assertEqual(match_hand_to_arm([], sample.arm_keypoints, 640, 480), [])
        for hands in ([other_hand, selected_hand], [selected_hand, other_hand]):
            self.assertEqual(tuple(match_hand_to_arm(hands, sample.arm_keypoints, 640, 480)),
                             sample.hand_keypoints)

    def test_pose_confidence_hysteresis_keeps_fresh_elbow_jitter_but_rejects_loss(self):
        raw = make_sample(1, 0, 0, u=.7)
        tracked = False
        controller = Controller()
        for i in range(60):
            quality = .6 if i % 2 == 0 else .48
            arm = dict(raw.arm_keypoints, elbow=(*raw.arm_keypoints["elbow"][:3], quality, .99))
            sample = sample_from_landmarks(raw.hand_keypoints, arm, 640, 480,
                                          i, i/60, i/60, pose_tracked=tracked)
            tracked = sample.pose_valid
            self.assertTrue(sample.valid)
            command = controller.update(sample, SimStatus(C.home_xyz, True), i/60)
            self.assertFalse(command.hold_position)
        self.assertGreater(command.target_xyz[0], C.home_xyz[0]+.05)
        # Actual occlusion or disappearance breaks the latch immediately.
        for arm in ({}, dict(raw.arm_keypoints, elbow=(.5, .5, 0, .1, .99)),
                    dict(raw.arm_keypoints, elbow=(float("nan"), .5, 0, .9, .99)),
                    dict(raw.arm_keypoints, elbow=(1.2, .5, 0, .9, .99))):
            sample = sample_from_landmarks(raw.hand_keypoints, arm, 640, 480,
                                          61, 61/60, 61/60, pose_tracked=True)
            self.assertFalse(sample.pose_valid)
            command = controller.update(sample, SimStatus(C.home_xyz, True), 61/60)
            self.assertTrue(command.hold_position)
        moderate = dict(raw.arm_keypoints, elbow=(.5, .5, 0, .48, .99))
        sample = sample_from_landmarks(raw.hand_keypoints, moderate, 640, 480, 62, 2, 2)
        self.assertFalse(sample.valid)  # Must reacquire, not resume at the retain floor.

    @unittest.skipUnless(importlib.util.find_spec("mediapipe"), "Install vision runtime")
    def test_inference_pairs_selected_side_on_the_same_frame_and_timestamp(self):
        import numpy as np
        from types import SimpleNamespace as NS
        from unittest.mock import Mock
        from vision import Vision
        for side, indices in (("Right", (11, 13, 15)), ("Left", (12, 14, 16))):
            config = replace(C, hand_side=side)
            raw = make_sample(1, 1, 1, u=.7, v=.65, side=side)
            pose = [NS(x=.05, y=.05, z=0, visibility=1, presence=1) for _ in range(33)]
            for index, name in zip(indices, ("shoulder", "elbow", "wrist")):
                x, y, z, visibility, presence = raw.arm_keypoints[name]
                pose[index] = NS(x=x, y=y, z=z, visibility=visibility, presence=presence)
            points = [NS(x=x, y=y, z=z) for x, y, z in raw.hand_keypoints]
            wrong = [NS(x=.05, y=.05, z=0)] * 21
            vision = Vision(config)
            vision._pose_model = Mock()
            vision._pose_model.detect_for_video.return_value = NS(pose_landmarks=[pose])
            vision._model = Mock()
            vision._model.detect_for_video.return_value = NS(
                hand_landmarks=[wrong, points],
                # Reproduce the webcam failure: the matching hand has the
                # opposite label; filtering by category picks the other arm.
                handedness=[[NS(category_name=side)],
                            [NS(category_name="Left" if side == "Right" else "Right")]])
            sample, _ = vision._infer(np.zeros((480, 640, 3), dtype=np.uint8), 1, 1, 1000)
            self.assertTrue(sample.valid)
            self.assertEqual(sample.arm_side, side)
            self.assertEqual(sample.hand_keypoints, raw.hand_keypoints)
            pose_args = vision._pose_model.detect_for_video.call_args.args
            hand_args = vision._model.detect_for_video.call_args.args
            self.assertIs(pose_args[0], hand_args[0])
            self.assertEqual(pose_args[1], hand_args[1])
            controller = Controller(config)
            for i in range(1, 61):
                now = i / 60
                command = controller.update(replace(sample, frame_id=i, captured_at=now,
                                                    processed_at=now), SimStatus(C.home_xyz, True), now)
            self.assertEqual(controller.state, State.READY)
            self.assertFalse(command.hold_position)
            self.assertGreater(command.target_xyz[0], C.home_xyz[0] + .05)
            self.assertLess(command.target_xyz[1], C.home_xyz[1] - .05)
            # Check the actual Vision latch, including reset after a frame gap.
            elbow = pose[indices[1]]
            for frame_id, captured, quality, expected in (
                    (2, 1.03, .48, True), (3, 1.06, .2, False),
                    (4, 1.09, .48, False), (5, 1.12, .8, True),
                    (6, 2.0, .48, False)):
                elbow.visibility = quality
                current, _ = vision._infer(np.zeros((480, 640, 3), dtype=np.uint8),
                                           frame_id, captured, int(captured*1000))
                self.assertEqual(current.pose_valid, expected)

    @unittest.skipUnless(importlib.util.find_spec("mediapipe") and Path("models/hand_landmarker.task").is_file(),
                         "Install MediaPipe and download the model for the worker smoke test")
    def test_real_model_video_workers_publish_invalid_and_close(self):
        import cv2
        import numpy as np
        from vision import Vision
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "blank.avi")
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 240))
            self.assertTrue(writer.isOpened())
            for _ in range(150):
                writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
            writer.release()
            vision = Vision(replace(C, camera_source=path))
            try:
                vision.start()
                deadline = time.monotonic() + 4
                while vision.latest_sample() is None and time.monotonic() < deadline:
                    time.sleep(.02)
                sample = vision.latest_sample()
                self.assertIsNotNone(sample, vision.error)
                self.assertFalse(sample.valid)
                self.assertGreater(sample.frame_id, 0)
                self.assertGreaterEqual(sample.processed_at, sample.captured_at)
            finally:
                vision.close()
            self.assertFalse(vision._capture_thread.is_alive())
            self.assertFalse(vision._process_thread.is_alive())


class MetricsTests(unittest.TestCase):
    def test_success_wrong_box_timeout_and_reset_are_all_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            metrics = Metrics(directory=directory)
            metrics.begin_trial(0)
            metrics.record_event({"timestamp": 1, "event_type": "picked", "box_id": "green"})
            metrics.record_event({"timestamp": 2, "event_type": "placed", "box_id": "green"})
            metrics.begin_trial(3)
            metrics.record_event({"timestamp": 4, "event_type": "picked", "box_id": "red"})
            metrics.record_event({"timestamp": 5, "event_type": "placed", "box_id": "red"})
            metrics.begin_trial(6)
            metrics.tick(36)
            metrics.begin_trial(37)
            metrics.record_event({"timestamp": 38, "event_type": "reset"})
            metrics.close()
            with (metrics.directory / "trials.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual([row["failure_reason"] for row in rows], ["", "wrong_box", "timeout_30s", "reset"])
            events = [json.loads(line) for line in (metrics.directory / "events.jsonl").read_text().splitlines()]
            self.assertEqual(events[1]["trial_id"], "1")


class BridgeTests(unittest.TestCase):
    def test_snapshot_input_and_direct_command_rejection(self):
        bridge = IntegrationBridge(0)
        base = f"http://127.0.0.1:{bridge.server.server_port}"
        try:
            bridge.publish({"active": True, "ee_xyz": [.5, 0, .35]})
            with urllib.request.urlopen(base + "/api/state") as response:
                self.assertEqual(json.load(response)["ee_xyz"], [.5, 0, .35])
            request = urllib.request.Request(base + "/api/input", data=b'{"key":"p"}', headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.status, 202)
            self.assertEqual(bridge.poll_key(), "p")
            self.assertIsNone(bridge.poll_key())
            request = urllib.request.Request(base + "/api/command", data=b'{}', headers={"Content-Type": "application/json"})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 409)
            request = urllib.request.Request(base + "/api/input", data=b'{"key":"r"}',
                                             headers={"Content-Type": "application/json", "Origin": "https://unrelated.example"})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 403)
        finally:
            bridge.close()


@unittest.skipUnless(importlib.util.find_spec("pybullet"), "Install the simulation runtime to run physics tests")
class PhysicsTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation(replace(C, simulation_gui=False))
        self.sim.initialize()
        self.controller = Controller()
        self.frame = 0
        self.now = 0
        self.events = []

    def tearDown(self):
        self.sim.close()

    def frames(self, count, x=.5, y=-.18, ratio=.8, valid=True):
        for _ in range(count):
            self.now += 1 / 60
            self.frame += 1
            u = .15 + (x - .35) / .30 * .7
            v = .15 + (.25 - y) / .5 * .7
            sample = make_sample(self.frame, self.now, self.now, valid, u, v, ratio)
            command = self.controller.update(sample, self.sim.status(), self.now)
            self.sim.step(command, 1 / 60)
            if command.action.value == "ATTACH":
                self.sim.try_attach(command.box_id)
            elif command.action.value == "RELEASE":
                self.sim.release()
            self.events.extend(self.controller.drain_events())

    def test_all_three_boxes_through_controller_and_real_physics(self):
        for box_id, pick_x, drop_x in (("red", .4, .43), ("green", .5, .5), ("blue", .6, .57)):
            self.frames(120, x=pick_x)
            self.frames(180, x=pick_x, ratio=.1)
            self.assertEqual(self.sim.status().held_box_id, box_id, self.events[-8:])
            self.frames(180, x=drop_x, y=.18, ratio=.1)
            self.frames(240, x=drop_x, y=.18)
            self.assertIn(box_id, self.sim.status().placed_box_ids, self.events[-8:])
        self.assertEqual(self.sim.status().placed_box_ids, frozenset({"red", "green", "blue"}))
        self.assertEqual(sum(e.event_type == "placed" for e in self.events), 3)

    def test_attach_distance_pause_held_object_and_reset(self):
        self.assertFalse(self.sim.try_attach("green"))
        self.frames(120)
        self.frames(180, ratio=.1)
        self.assertEqual(self.sim.held, "green")
        position = self.sim.status().ee_xyz
        self.frames(120, valid=False)
        self.assertEqual(self.controller.state, State.PAUSED)
        self.assertEqual(self.sim.held, "green")
        self.assertLess(dist(position, self.sim.status().ee_xyz), .015)
        self.assertTrue(self.sim.try_attach("green"))  # idempotent, no second constraint
        self.assertEqual(self.sim.p.getNumConstraints(), 1)
        self.sim.reset()
        self.controller.reset()
        self.assertIsNone(self.sim.held)
        self.assertEqual(self.sim.p.getNumConstraints(), 0)
        self.assertFalse(self.sim.placed)

    def test_box_never_grasped_and_released_is_not_a_success(self):
        self.sim.p.resetBasePositionAndOrientation(self.sim.boxes["green"],
                                                   (*C.bin_center, .04), (0, 0, 0, 1))
        for _ in range(120):
            self.sim.step(RobotCommand(C.home_xyz, False), 1 / 60)
        self.assertNotIn("green", self.sim.status().placed_box_ids)

    def test_pause_latches_joints_instead_of_resolving_ik(self):
        self.frames(120)
        self.frames(180, ratio=.1)
        command = self.controller.update(None, self.sim.status(), self.now + .01)
        self.assertTrue(command.hold_position)
        self.sim.step(command, 1 / 60)
        captured = tuple(self.sim._hold_joints)
        for _ in range(120):
            self.sim.step(command, 1 / 60)
        self.assertEqual(tuple(self.sim._hold_joints), captured)
        actual = [self.sim.p.getJointState(self.sim.robot, i)[0] for i in range(7)]
        self.assertLess(max(abs(a-b) for a, b in zip(actual, captured)), .005)
        self.assertEqual(self.sim.status().held_box_id, "green")
        self.sim.reset()
        self.assertIsNone(self.sim._hold_joints)

    def test_standalone_simulation_runner_uses_real_feedback(self):
        from dev.run_simulation import run_sequence
        status = run_sequence(self.sim, self.sim.config, "blue", realtime=False)
        self.assertEqual(status.placed_box_ids, frozenset({"blue"}))
        self.assertIsNone(status.held_box_id)

    def test_ik_reaches_workspace_corners_and_pick_bin_heights(self):
        points = [(x, y, C.transport_z) for x in C.workspace_x for y in C.workspace_y]
        points += [(xyz[0], xyz[1], C.pick_z) for _, xyz, _ in C.boxes]
        points += [(*C.bin_center, C.place_z)]
        for point in points:
            for _ in range(120):
                status = self.sim.step(RobotCommand(point, False), 1 / 60)
            self.assertLess(dist(status.ee_xyz, point), C.position_tolerance, point)


if __name__ == "__main__":
    unittest.main()
