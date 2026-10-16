"""Latest-frame MediaPipe adapter. No simulator calls or gesture decisions here."""

from math import dist, isfinite
from pathlib import Path
import threading
import time

from config import DEFAULT_CONFIG
from contracts import HandSample


def sample_from_landmarks(points, width, height, frame_id, captured_at, processed_at):
    """Pixel-correct thumb/index ratio and mirrored palm center, stdlib-testable."""
    invalid = HandSample(frame_id, captured_at, processed_at, False)
    if len(points) != 21 or width <= 0 or height <= 0:
        return invalid
    if not all(isfinite(x) for point in points for x in point[:2]):
        return invalid
    pixels = [(q[0] * width, q[1] * height) for q in points]
    scale = dist(pixels[0], pixels[9])
    if scale < 15:
        return invalid
    palm = [points[i] for i in (0, 5, 9, 13, 17)]
    u, v = (sum(p[i] for p in palm) / len(palm) for i in (0, 1))
    if not (0 <= u <= 1 and 0 <= v <= 1):
        return invalid
    return HandSample(frame_id, captured_at, processed_at, True, u, v,
                      dist(pixels[4], pixels[8]) / scale)


class Vision:
    def __init__(self, config=DEFAULT_CONFIG):
        self.config = config
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._sample = self._overlay = self._frame = None
        self._capture_thread = self._process_thread = None
        self._cap = self._model = None
        self.error = None

    def start(self):
        import cv2
        import mediapipe as mp
        path = Path(self.config.hand_model)
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}; run python -m dev.download_model")
        self._model = mp.tasks.vision.HandLandmarker.create_from_options(
            mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
                min_hand_detection_confidence=.6, min_hand_presence_confidence=.6,
                min_tracking_confidence=.6))
        self._cap = cv2.VideoCapture(self.config.camera_source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera/video {self.config.camera_source!r}")
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._capture_thread = threading.Thread(target=self._capture, daemon=True)
        self._process_thread = threading.Thread(target=self._process, daemon=True)
        self._capture_thread.start()
        self._process_thread.start()

    def _invalidate(self, reason):
        self.error = reason
        with self._lock:
            now = time.monotonic()
            frame_id = self._frame[0] if self._frame else 0
            self._sample = HandSample(frame_id, now, now, False)

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
        import cv2
        import mediapipe as mp
        last_id = last_ms = -1
        # Never transfer ownership to the other hand when the selected side vanishes.
        previous = None
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
                result = self._model.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), timestamp)
                choices = [landmarks for landmarks, handedness in zip(result.hand_landmarks, result.handedness)
                           if handedness and handedness[0].category_name == self.config.hand_side]
                points = []
                if choices:
                    chosen = min(choices, key=lambda hand: dist((hand[0].x, hand[0].y), previous)) if previous else choices[0]
                    points = [(p.x, p.y, p.z) for p in chosen]
                    previous = points[0][:2]
                h, w = frame.shape[:2]
                sample = sample_from_landmarks(points, w, h, frame_id, captured, time.monotonic())
                overlay = frame.copy()
                left, top, right, bottom = self.config.image_rect
                cv2.rectangle(overlay, (int(left*w), int(top*h)), (int(right*w), int(bottom*h)), (255, 180, 0), 2)
                if points:
                    # Use TV2's shared landmark rendering and topology.
                    import numpy as np
                    from run_holistic import draw_hand
                    draw_hand(overlay, np.array(points), w, h)
                if sample.valid:
                    cv2.circle(overlay, (int(sample.u*w), int(sample.v*h)), 9, (0, 255, 255), 2)
                text = f"{self.config.hand_side} hand | pinch={sample.pinch_ratio:.2f}" if sample.valid else "NO SELECTED HAND"
                cv2.putText(overlay, text, (12, h-16), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
                with self._lock:
                    if not self._stop.is_set():
                        self._sample, self._overlay = sample, overlay
        except Exception as exc:
            self._invalidate(str(exc))
            self._stop.set()

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
        if any(worker is not None and worker.is_alive()
               for worker in (self._capture_thread, self._process_thread)):
            raise RuntimeError("Camera/inference worker did not stop within 3 seconds")
