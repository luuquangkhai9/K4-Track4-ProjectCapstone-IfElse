"""Luồng perception: webcam -> MediaPipe -> fusion -> bộ đệm "frame mới nhất".

Luồng chính (mô phỏng / hiển thị) chỉ đọc frame mới nhất, không bao giờ chờ perception,
nên mô phỏng luôn mượt kể cả khi perception chạy chậm trên CPU.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, TypeVar

import cv2
import numpy as np

from perception.fusion import HAND_CONNECTIONS, POSE_IDX, ArmHandFrame, ArmHandFusion, finger_of
from perception.landmarker import Landmarker, RawDetection

T = TypeVar("T")


@dataclass
class PerceptionOutput:
    frames: dict[str, ArmHandFrame]
    fps: float
    image: np.ndarray | None = None          # ảnh webcam đã vẽ keypoint (để hiển thị)
    extra: dict = field(default_factory=dict)


class LatestBuffer(Generic[T]):
    """Bộ đệm 1 phần tử, thread-safe. Ghi đè liên tục; người đọc nhận bản mới nhất + số thứ tự."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._item: T | None = None
        self._seq = 0

    def put(self, item: T) -> None:
        with self._lock:
            self._item = item
            self._seq += 1

    def get(self) -> tuple[int, T | None]:
        with self._lock:
            return self._seq, self._item


class FpsMeter:
    def __init__(self, alpha: float = 0.1) -> None:
        self.alpha, self.fps, self._last = alpha, 0.0, None

    def tick(self, now: float) -> float:
        if self._last is not None and now > self._last:
            inst = 1.0 / (now - self._last)
            self.fps = inst if self.fps == 0 else (1 - self.alpha) * self.fps + self.alpha * inst
        self._last = now
        return self.fps


ARM_COLOR_BGR = (235, 140, 60)
FINGER_COLOR_BGR = {"palm": (220, 220, 220), "thumb": (80, 80, 240), "index": (40, 150, 255),
                    "middle": (50, 230, 240), "ring": (100, 220, 80), "pinky": (240, 100, 180)}


def draw_overlay(image: np.ndarray, det: RawDetection, fusion: ArmHandFusion) -> None:
    """Vẽ keypoint 2D (cánh tay theo pose + bàn tay đã ghép) lên ảnh KHÔNG lật gương."""
    h, w = image.shape[:2]

    def px(p: np.ndarray) -> tuple[int, int]:
        return int(p[0] * w), int(p[1] * h)

    if det.pose_image is not None:
        for s in fusion.sides:
            a, b, c = (det.pose_image[i] for i in POSE_IDX[s])
            cv2.line(image, px(a), px(b), ARM_COLOR_BGR, 4)
            cv2.line(image, px(b), px(c), ARM_COLOR_BGR, 4)
            for p in (a, b, c):
                cv2.circle(image, px(p), 7, (255, 255, 255), -1)
    for s, hand in fusion.matched.items():
        for a, b in HAND_CONNECTIONS:
            cv2.line(image, px(hand.image[a]), px(hand.image[b]), FINGER_COLOR_BGR[finger_of(b)], 2)
        for i, p in enumerate(hand.image):
            cv2.circle(image, px(p), 3, FINGER_COLOR_BGR[finger_of(i)], -1)
    # Tay phát hiện được nhưng không ghép được với pose: vẽ xám
    for hand in det.hands:
        if not any(hand is m for m in fusion.matched.values()):
            for a, b in HAND_CONNECTIONS:
                cv2.line(image, px(hand.image[a]), px(hand.image[b]), (128, 128, 128), 1)


def open_camera(cam_cfg: dict) -> cv2.VideoCapture:
    cam_id = int(cam_cfg.get("id", 0))
    # Trên Windows, DirectShow mở camera nhanh hơn MSMF rất nhiều
    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
    cap = cv2.VideoCapture(cam_id, backend)
    if not cap.isOpened():
        cap = cv2.VideoCapture(cam_id)
    if not cap.isOpened():
        raise RuntimeError(f"Không mở được camera id={cam_id}")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(cam_cfg.get("width", 1280)))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(cam_cfg.get("height", 720)))
    cap.set(cv2.CAP_PROP_FPS, int(cam_cfg.get("fps", 30)))
    return cap


class CameraPerceptionThread(threading.Thread):
    """Đọc webcam, chạy landmarker + fusion, ghi PerceptionOutput mới nhất vào `buffer`."""

    def __init__(self, cfg: dict, buffer: LatestBuffer[PerceptionOutput], models_dir: Path) -> None:
        super().__init__(name="perception", daemon=True)
        self.cfg, self.buffer, self.models_dir = cfg, buffer, models_dir
        self._stop_event = threading.Event()
        self.error: BaseException | None = None
        self.ready = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        cap = None
        landmarker = None
        try:
            cam_cfg, disp_cfg = self.cfg.get("camera", {}), self.cfg.get("display", {})
            landmarker = Landmarker(self.cfg.get("perception", {}), self.models_dir)
            fusion = ArmHandFusion(self.cfg.get("perception", {}), self.cfg.get("filter", {}))
            cap = open_camera(cam_cfg)
            self.ready.set()
            meter = FpsMeter()
            fails = 0
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    fails += 1
                    if fails > 50:
                        raise RuntimeError("Camera không trả về frame")
                    time.sleep(0.01)
                    continue
                fails = 0
                t = time.monotonic()
                if cam_cfg.get("source_mirrored", False):
                    frame = cv2.flip(frame, 1)  # đưa về ảnh không lật gương trước khi suy luận
                det = landmarker.detect(frame, t)
                frames = fusion.update(det)
                fps = meter.tick(time.monotonic())

                draw_overlay(frame, det, fusion)
                if disp_cfg.get("mirror", True):
                    frame = cv2.flip(frame, 1)  # chỉ lật để HIỂN THỊ như gương, dữ liệu 3D không đổi
                status = "  ".join(f"{s}:{'OK' if f.valid else '--'}" for s, f in frames.items())
                cv2.putText(frame, f"Perception FPS: {fps:5.1f}   {status}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
                self.buffer.put(PerceptionOutput(frames=frames, fps=fps, image=frame))
        except BaseException as exc:  # báo lỗi cho luồng chính
            self.error = exc
        finally:
            self.ready.set()
            if cap is not None:
                cap.release()
            if landmarker is not None:
                landmarker.close()
