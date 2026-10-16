from dataclasses import replace
import importlib.util
from math import dist, isfinite
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from arm_control import ArmController, arm_vectors
from arm_vision import sample_from_pose
from config import DEFAULT_CONFIG as C
from contracts import ArmSample, ControllerState as State, RobotCommand, SimStatus
from simulation import Simulation


def arm(frame, now, elbow=(.12,.18,-.05), wrist=(.18,.25,-.25), shoulder=(0,0,0), valid=True):
    return ArmSample(frame, now, now, valid, shoulder, elbow, wrist)


class ArmControlTests(unittest.TestCase):
    def test_cli_passes_arm_config_into_loop(self):
        import main
        with patch('sys.argv',['main.py','--mode','arm','--demo','--headless','--no-log']), patch('main.run') as run:
            main.main()
        self.assertEqual(run.call_args.kwargs['config'].control_mode,'arm')
        self.assertEqual(run.call_args.args[0].__class__.__module__,'dev.scripted_arm')

    def setUp(self):
        self.controller = ArmController()
        self.status = SimStatus((.5,0,.35), True, elbow_xyz=(.1,0,.55))
        self.now = 0
        self.frame = 0

    def tick(self, **kwargs):
        self.now += 1/60
        self.frame += 1
        return self.controller.update(arm(self.frame,self.now,**kwargs), self.status, self.now)

    def calibrate(self):
        self.tick()
        self.controller.request_resume()
        for _ in range(50): self.tick()
        self.assertEqual(self.controller.state, State.FOLLOWING)

    def test_calibration_requires_explicit_confirmation_and_fresh_frames(self):
        for _ in range(60): self.tick()
        self.assertEqual(self.controller.state, State.PAUSED)
        self.controller.request_resume()
        self.tick()
        sample = arm(self.frame, self.now)
        for _ in range(10):
            self.controller.update(sample,self.status,self.now+.1)
        self.assertEqual(self.controller.state, State.CALIBRATING)

    def test_translation_and_body_size_do_not_move_robot(self):
        self.calibrate()
        source = arm(100,self.now)
        transform = lambda point: tuple(1.2*x+offset for x,offset in zip(point,(.3,.1,.2)))
        for _ in range(100):
            command = self.tick(shoulder=transform(source.shoulder_xyz),
                                elbow=transform(source.elbow_xyz), wrist=transform(source.wrist_xyz))
        self.assertLess(dist(command.target_xyz,self.status.ee_xyz),1e-9)
        self.assertLess(dist(command.elbow_xyz,self.status.elbow_xyz),1e-9)

    def test_arm_moves_wrist_and_elbow_with_rate_limits(self):
        self.calibrate()
        previous = self.controller.target
        old_elbow = self.controller.elbow
        for _ in range(120):
            command = self.tick(elbow=(.16,.10,-.10),wrist=(.26,.12,-.3))
            self.assertLessEqual(dist(previous,command.target_xyz),C.max_speed/60+1e-9)
            self.assertLessEqual(dist(old_elbow,command.elbow_xyz),C.max_speed/60+1e-9)
            previous,old_elbow=command.target_xyz,command.elbow_xyz
        self.assertGreater(command.target_xyz[2], self.status.ee_xyz[2]+.05)
        self.assertGreater(dist(command.elbow_xyz,self.status.elbow_xyz), .02)
        self.assertEqual(command.action.value,"NONE")

    def test_loss_holds_actual_joints_and_requires_recalibration(self):
        self.calibrate()
        self.tick(wrist=(.26,.12,-.3))
        command=self.tick(valid=False)
        self.assertTrue(command.hold_position)
        self.assertEqual(command.target_xyz,self.status.ee_xyz)
        for _ in range(60): self.tick()
        self.assertEqual(self.controller.state,State.PAUSED)
        self.controller.request_resume()
        for _ in range(50): command=self.tick()
        self.assertEqual(self.controller.state,State.FOLLOWING)
        self.assertLess(dist(command.target_xyz,self.status.ee_xyz),1e-9)

    def test_stale_nan_and_implausible_arm_pause(self):
        for sample in (arm(1,0),arm(1,1,wrist=(float('nan'),0,0)),arm(1,1,elbow=(0,0,0))):
            self.controller.update(sample,self.status,1)
            self.assertEqual(self.controller.state,State.PAUSED)

    def test_pose_visibility_selected_side_and_missing_wrist(self):
        landmarks=[SimpleNamespace(x=.5,y=.5,visibility=1) for _ in range(33)]
        world=[SimpleNamespace(x=0,y=0,z=0) for _ in range(33)]
        for index,point in zip((12,14,16),((0,0,0),(.12,.18,-.05),(.18,.25,-.25))):
            world[index]=SimpleNamespace(x=point[0],y=point[1],z=point[2])
        sample=sample_from_pose(landmarks,world,'Right',1,1,1)
        self.assertTrue(sample.valid)
        landmarks[16].visibility=.2
        self.assertFalse(sample_from_pose(landmarks,world,'Right',2,2,2).valid)
        self.assertFalse(sample_from_pose(None,world,'Right',2,2,2).valid)


@unittest.skipUnless(importlib.util.find_spec('pybullet'),'Install physics runtime')
class ArmPhysicsTests(unittest.TestCase):
    def test_robot_and_actual_elbow_follow_then_freeze(self):
        config=replace(C,simulation_gui=False,control_mode='arm')
        simulation=Simulation(config)
        controller=ArmController(config)
        now=0
        try:
            simulation.initialize()
            initial=simulation.status()
            for frame in range(1,301):
                now+=1/60
                if frame==2: controller.request_resume()
                sample=arm(frame,now) if frame<80 else arm(frame,now,elbow=(.16,.10,-.10),wrist=(.26,.12,-.3))
                command=controller.update(sample,simulation.status(),now)
                simulation.step(command,1/60)
            moved=simulation.status()
            self.assertEqual(controller.state,State.FOLLOWING)
            self.assertGreater(dist(initial.ee_xyz,moved.ee_xyz),.04)
            self.assertGreater(dist(initial.elbow_xyz,moved.elbow_xyz),.015)
            self.assertGreater(moved.ee_xyz[2],initial.ee_xyz[2]+.03)
            for frame in range(301,421):
                now+=1/60
                command=controller.update(arm(frame,now,valid=False),simulation.status(),now)
                simulation.step(command,1/60)
            self.assertEqual(controller.state,State.PAUSED)
            self.assertLess(dist(moved.ee_xyz,simulation.status().ee_xyz),.015)
            for i in range(7):
                info=simulation.p.getJointInfo(simulation.robot,i)
                q=simulation.p.getJointState(simulation.robot,i)[0]
                self.assertTrue(isfinite(q) and info[8]-.01<=q<=info[9]+.01)
            self.assertEqual(len(simulation.snapshot()['robot_links']),9)
        finally:
            simulation.close()


@unittest.skipUnless(importlib.util.find_spec('mediapipe'),'Install MediaPipe runtime')
class HolisticSmokeTests(unittest.TestCase):
    def test_real_holistic_worker_missing_arm_is_invalid(self):
        import cv2
        import numpy as np
        from arm_vision import Vision
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'blank.avi')
            writer=cv2.VideoWriter(path,cv2.VideoWriter_fourcc(*'MJPG'),30,(320,240))
            self.assertTrue(writer.isOpened())
            for _ in range(150): writer.write(np.zeros((240,320,3),np.uint8))
            writer.release()
            vision=Vision(replace(C,camera_source=path,control_mode='arm'))
            try:
                vision.start()
                deadline=time.monotonic()+4
                while vision.latest_sample() is None and time.monotonic()<deadline: time.sleep(.02)
                sample=vision.latest_sample()
                self.assertIsInstance(sample,ArmSample,vision.error)
                self.assertFalse(sample.valid)
            finally:
                vision.close()
            self.assertFalse(vision._capture_thread.is_alive())
            self.assertFalse(vision._process_thread.is_alive())


if __name__=='__main__':
    unittest.main()
