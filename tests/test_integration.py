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
from contracts import HandSample, RobotCommand, ControllerState as State
from control import Controller
from metrics import Metrics
from simulation import Simulation
from simulation.serve import IntegrationBridge
from vision import sample_from_landmarks


class VisionGeometryTests(unittest.TestCase):
    def test_pixel_aspect_ratio_and_palm_center(self):
        points = [(.5, .5, 0)] * 21
        points[0] = (.5, .7, 0)
        points[4], points[8] = (.4, .5, 0), (.45, .5, 0)
        sample = sample_from_landmarks(points, 640, 480, 1, 1, 1.01)
        self.assertTrue(sample.valid)
        self.assertAlmostEqual(sample.pinch_ratio, 32 / 96)
        self.assertAlmostEqual(sample.u, .5)
        self.assertAlmostEqual(sample.v, .54)

    def test_missing_tiny_or_nonfinite_hand_is_invalid(self):
        for points in ([], [(.5, .5, 0)] * 21, [(float("nan"), .5, 0)] * 21):
            self.assertFalse(sample_from_landmarks(points, 640, 480, 1, 1, 1).valid)

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
            sample = HandSample(self.frame, self.now, self.now, valid, u, v, ratio)
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
