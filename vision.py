"""Latest-frame MediaPipe adapter. No simulator calls or gesture decisions here."""

from math import dist, isfinite
from pathlib import Path
import threading
import time

from config import DEFAULT_CONFIG
from contracts import HandSample

HAND_EDGES = ((0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
              (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14),
              (14, 15), (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20))


def match_hand_to_arm(hands, arm, width, height, config=DEFAULT_CONFIG):
    """The selected pose wrist owns the hand; handedness labels cannot swap it.

    Pose and Hands can disagree about Left/Right on mirrored camera input.
    Use the spatial correspondence on their shared frame, and never fall back
    to a hand on the other arm when the selected wrist/hand disappears.
    """
    wrist = arm.get("wrist")
    if wrist is None or not all(isfinite(v) for v in wrist[:2]):
        return []
    choices = []
    for hand in hands:
        if len(hand) != 21 or not all(isfinite(v) for v in (hand[0].x, hand[0].y)):
            continue
        distance = dist((hand[0].x * width, hand[0].y * height),
                        (wrist[0] * width, wrist[1] * height))
        if distance <= config.wrist_match_max_ratio * min(width, height):
            choices.append((distance, hand))
    if not choices:
        return []
    chosen = min(choices, key=lambda choice: choice[0])[1]
    return [(p.x, p.y, p.z) for p in chosen]


def sample_from_landmarks(points, arm, width, height, frame_id, captured_at,
                          processed_at, config=DEFAULT_CONFIG, *, pose_tracked=False):
    """Publish raw same-frame landmarks, retaining partial results for overlay."""
    hand_valid = len(points) == 21 and all(
        len(p) == 3 and all(isfinite(v) for v in p)
        and all(0 <= v <= 1 for v in p[:2]) for p in points)
    threshold = config.pick_pose_retain if pose_tracked else config.pick_pose_acquire
    pose_valid = all(name in arm and len(arm[name]) == 5
                     and all(isfinite(v) for v in arm[name])
                     and all(0 <= v <= 1 for v in arm[name][:2])
                     and all(threshold <= v <= 1 for v in arm[name][3:])
                     for name in ("shoulder", "elbow", "wrist"))
    matched = (hand_valid and pose_valid and width > 0 and height > 0
               and dist((points[0][0]*width, points[0][1]*height),
                        (arm["wrist"][0]*width, arm["wrist"][1]*height))
               <= config.wrist_match_max_ratio * min(width, height))
    return HandSample(frame_id, captured_at, processed_at, bool(matched),
                      config.hand_side, arm, tuple(points), pose_valid, hand_valid, width, height)


class Vision:
    def __init__(self, config=DEFAULT_CONFIG):
        self.config = config
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._sample = self._overlay = self._frame = None
        self._capture_thread = self._process_thread = None
        self._cap = self._model = self._pose_model = None
        self.error = None
        self.is_synthetic = False
        self._pose_tracked = False
        self._last_pose_capture = None

    def start(self):
        import cv2
        self._model = self._create_model()
        self._cap = cv2.VideoCapture(self.config.camera_source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera/video {self.config.camera_source!r}")
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._capture_thread = threading.Thread(target=self._capture, daemon=True)
        self._process_thread = threading.Thread(target=self._process, daemon=True)
        self._capture_thread.start()
        self._process_thread.start()

    def _create_model(self):
        import mediapipe as mp
        path = Path(self.config.hand_model)
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}; run python -m dev.download_model")
        hand = mp.tasks.vision.HandLandmarker.create_from_options(
            mp.tasks.vision.HandLandmarkerOptions(
                # Holistic changes MediaPipe's process-wide resource directory.
                # Loading bytes keeps Tasks usable after a Holistic graph on Windows.
                base_options=mp.tasks.BaseOptions(model_asset_buffer=path.read_bytes()),
                running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
                min_hand_detection_confidence=.6, min_hand_presence_confidence=.6,
                min_tracking_confidence=.6))

        try:
            pose_path = Path(self.config.pose_model)
            if not pose_path.is_file():
                raise FileNotFoundError(f"Missing {pose_path}; run python -m dev.download_model")
            self._pose_model = mp.tasks.vision.PoseLandmarker.create_from_options(
                mp.tasks.vision.PoseLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_buffer=pose_path.read_bytes()),
                    running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1,
                    min_pose_detection_confidence=.6, min_pose_presence_confidence=.6,
                    min_tracking_confidence=.6))
        except Exception:
            hand.close()
            raise
        return hand

    def _invalidate(self, reason):
        self.error = reason
        with self._lock:
            now = time.monotonic()
            frame_id = self._frame[0] if self._frame else 0
            self._sample = self._invalid_sample(frame_id, now)

    def _invalid_sample(self, frame_id, now):
        return HandSample(frame_id, now, now, False)

    def _capture(self):
        import cv2
        frame_id = 0
        try:
            while not self._stop.is_set():
                ok, frame = self._cap.read()
                captured = time.monotonic()
                if not ok:
                    self._invalidate("camera_read_failed_or_end_of_video")
                    self._stop.set()
                    with self._condition:
                        self._condition.notify_all()
                    break
                frame_id += 1
                frame = cv2.flip(frame, 1)
                with self._condition:
                    self._frame = (frame_id, captured, frame)
                    self._condition.notify_all()
                # Pace file playback; cameras already block at their own frame rate.
                if isinstance(self.config.camera_source, str):
                    fps = self._cap.get(cv2.CAP_PROP_FPS) or 30
                    self._stop.wait(1 / max(1, fps))
        except Exception as exc:
            self._invalidate(str(exc))
            self._stop.set()
        finally:
            self._cap.release()

    def _process(self):
        last_id = last_ms = -1
        # Never transfer ownership to the other hand when the selected side vanishes.
        try:
            while not self._stop.is_set():
                with self._condition:
                    self._condition.wait_for(
                        lambda: self._stop.is_set() or (self._frame is not None and self._frame[0] != last_id),
                        timeout=.1)
                    if self._stop.is_set():
                        break
                    if self._frame is None or self._frame[0] == last_id:
                        continue
                    frame_id, captured, frame = self._frame
                last_id = frame_id
                timestamp = max(last_ms + 1, int(captured * 1000))
                last_ms = timestamp
                sample, overlay = self._infer(frame, frame_id, captured, timestamp)
                with self._lock:
                    if not self._stop.is_set():
                        self._sample, self._overlay = sample, overlay
        except Exception as exc:
            self._invalidate(str(exc))
            self._stop.set()

    def _infer(self, frame, frame_id, captured, timestamp):
        import cv2
        import mediapipe as mp
        image = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        # Both models consume the exact same mirrored frame and timestamp.
        pose = self._pose_model.detect_for_video(image, timestamp)
        result = self._model.detect_for_video(image, timestamp)
        arm = {}
        if pose.pose_landmarks:
            # Keep the configured physical arm on this mirrored pose frame.
            # Hand selection below uses its wrist, not a second side label.
            indices = (11, 13, 15) if self.config.hand_side == "Right" else (12, 14, 16)
            arm = {name: (p.x, p.y, p.z, p.visibility, p.presence)
                   for name, p in zip(("shoulder", "elbow", "wrist"),
                                      (pose.pose_landmarks[0][i] for i in indices))}
        h, w = frame.shape[:2]
        points = match_hand_to_arm(result.hand_landmarks, arm, w, h, self.config)
        if (self._last_pose_capture is not None
                and not 0 <= captured - self._last_pose_capture <= self.config.sample_max_age_s):
            self._pose_tracked = False
        self._last_pose_capture = captured
        sample = sample_from_landmarks(points, arm, w, h, frame_id, captured,
                                       time.monotonic(), self.config,
                                       pose_tracked=self._pose_tracked)
        # Only current-frame landmarks count. No cached elbow or grace period
        # can make an absent/occluded arm valid. Reacquire at the higher threshold.
        self._pose_tracked = sample.pose_valid
        overlay = frame.copy()
        left, top, right, bottom = self.config.image_rect
        cv2.rectangle(overlay, (int(left*w), int(top*h)), (int(right*w), int(bottom*h)), (255, 180, 0), 2)
        arm_pixels = []
        for name in ("shoulder", "elbow", "wrist"):
            point = arm.get(name)
            if (point and all(isfinite(v) for v in point)
                    and all(0 <= v <= 1 for v in point[:2])):
                pixel = (int(point[0]*w), int(point[1]*h))
                arm_pixels.append(pixel)
                quality = min(point[3:])
                color = ((0, 255, 0) if quality >= self.config.pick_pose_acquire else
                         (0, 200, 255) if quality >= self.config.pick_pose_retain else (0, 0, 255))
                cv2.circle(overlay, pixel, 6, color, -1)
                label = f"{name} v={point[3]:.2f} p={point[4]:.2f}"
                cv2.putText(overlay, label, (pixel[0]+7, pixel[1]), cv2.FONT_HERSHEY_SIMPLEX,
                            .4, color, 1)
        if sample.pose_valid:
            for a, b in zip(arm_pixels, arm_pixels[1:]):
                cv2.line(overlay, a, b, (255, 255, 0), 3)
        if sample.hand_valid:
            pixels = [(int(x*w), int(y*h)) for x, y, *_ in points]
            for a, b in HAND_EDGES:
                cv2.line(overlay, pixels[a], pixels[b], (0, 255, 0), 2)
            for point in pixels:
                cv2.circle(overlay, point, 3, (0, 0, 255), -1)
        text = (f"{self.config.hand_side} | pose={sample.pose_valid} hand={sample.hand_valid} "
                f"matched={sample.valid} | conveyor stopped")
        cv2.putText(overlay, text, (12, h-16), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 255), 1)
        if not sample.pose_valid:
            hint = "Show selected shoulder, elbow and wrist"
        elif not sample.hand_valid:
            hint = "Show the hand connected to the selected wrist"
        else:
            hint = "Open thumb/index, hold steady, then press C if PAUSED"
        cv2.putText(overlay, hint, (12, h-40), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 255), 1)
        if not sample.pose_valid and arm:
            weakest = min(arm, key=lambda name: min(arm[name][3:]))
            diagnostic = f"Weakest: {weakest} | acquire {self.config.pick_pose_acquire:.2f}, retain {self.config.pick_pose_retain:.2f}"
            cv2.putText(overlay, diagnostic, (12, h-64), cv2.FONT_HERSHEY_SIMPLEX,
                        .45, (0, 200, 255), 1)
        return sample, overlay

    def latest_sample(self):
        with self._lock:
            return self._sample

    def latest_overlay(self):
        with self._lock:
            return self._overlay

    def close(self):
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        if self._cap is not None and self._capture_thread is None:
            self._cap.release()
        for worker in (self._capture_thread, self._process_thread):
            if worker is not None:
                worker.join(timeout=3)
        if self._process_thread is None or not self._process_thread.is_alive():
            if self._model is not None:
                self._model.close()
                self._model = None
            if self._pose_model is not None:
                self._pose_model.close()
                self._pose_model = None
        if any(worker is not None and worker.is_alive()
               for worker in (self._capture_thread, self._process_thread)):
            raise RuntimeError("Camera/inference worker did not stop within 3 seconds")
