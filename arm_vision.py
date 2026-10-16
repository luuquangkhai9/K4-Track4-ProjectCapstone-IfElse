"""TV2 Holistic pose+hands on the integrated latest-frame worker lifecycle."""
from math import dist, isfinite
import time

from contracts import ArmSample
from vision import Vision as HandVision


def sample_from_pose(landmarks, world, side, frame_id, captured_at, processed_at, visibility=.65):
    invalid = ArmSample(frame_id, captured_at, processed_at, False)
    if landmarks is None or world is None or len(landmarks) < 33 or len(world) < 33:
        return invalid
    indices = (12, 14, 16) if side == "Right" else (11, 13, 15)
    for i in indices:
        point = landmarks[i]
        if (not all(isfinite(x) for x in (point.x, point.y, point.visibility))
                or point.visibility < visibility or not (0 <= point.x <= 1 and 0 <= point.y <= 1)):
            return invalid
    points = [tuple(getattr(world[i], axis) for axis in ("x", "y", "z")) for i in indices]
    if not all(isfinite(x) for point in points for x in point):
        return invalid
    if not all(.06 <= dist(a, b) <= .65 for a,b in zip(points, points[1:])):
        return invalid
    return ArmSample(frame_id, captured_at, processed_at, True, *points)


class Vision(HandVision):
    def _invalid_sample(self, frame_id, now):
        return ArmSample(frame_id, now, now, False)

    def _create_model(self):
        import mediapipe as mp
        return mp.solutions.holistic.Holistic(model_complexity=1, smooth_landmarks=True,
                                              min_detection_confidence=.6, min_tracking_confidence=.6)

    def _infer(self, frame, frame_id, captured, timestamp):
        import cv2
        import numpy as np
        from run_holistic import ARM_IDX, draw_hand
        result = self._model.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        landmarks = result.pose_landmarks.landmark if result.pose_landmarks else None
        world = result.pose_world_landmarks.landmark if result.pose_world_landmarks else None
        sample = sample_from_pose(landmarks, world, self.config.hand_side, frame_id,
                                  captured, time.monotonic(), self.config.arm_visibility)
        overlay = frame.copy()
        h, w = frame.shape[:2]
        # Draw both visible arms; exactly the selected side controls the robot.
        if landmarks:
            for side, indices in ARM_IDX.items():
                selected = (side == "R") == (self.config.hand_side == "Right")
                color = (0, 255, 255) if selected else (130, 130, 130)
                if min(landmarks[i].visibility for i in indices) < self.config.arm_visibility:
                    continue
                pixels = [(int(landmarks[i].x*w), int(landmarks[i].y*h)) for i in indices]
                for a,b in zip(pixels, pixels[1:]):
                    cv2.line(overlay, a, b, color, 4)
                for point, name in zip(pixels, ("shoulder", "elbow", "wrist")):
                    cv2.circle(overlay, point, 7, color, -1)
                    if selected:
                        cv2.putText(overlay, name, (point[0]+8, point[1]), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1)
        hand = result.right_hand_landmarks if self.config.hand_side == "Right" else result.left_hand_landmarks
        if hand:
            draw_hand(overlay, np.array([(p.x,p.y,p.z) for p in hand.landmark]), w, h)
        text = f"{self.config.hand_side} ARM XYZ | C calibrate | P pause" if sample.valid else "SHOW FULL SHOULDER - ELBOW - WRIST"
        cv2.putText(overlay, text, (12,h-16), cv2.FONT_HERSHEY_SIMPLEX, .5, (0,255,255), 2)
        return sample, overlay
