"""Bọc MediaPipe Tasks API: PoseLandmarker + HandLandmarker ở chế độ VIDEO.

Quy ước về lật gương (mirror):
- Ảnh đưa vào model LUÔN là ảnh KHÔNG lật gương (như camera nhìn thấy thật).
  Khi đó tọa độ 3D giữ đúng chiều (tay phải vẫn là tay phải về hình học) và
  chỉ số pose 11/13/15 = vai/khuỷu/cổ tay TRÁI thật của người.
- HandLandmarker gán nhãn Left/Right với giả định ảnh ĐÃ lật gương (camera selfie),
  nên với ảnh không lật ta phải ĐẢO nhãn: "Left" -> tay phải thật.
- Nếu driver webcam tự lật gương (camera.source_mirrored: true) ta lật lại trước khi suy luận.
"""
from __future__ import annotations

import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

_MODEL_ROOT = "https://storage.googleapis.com/mediapipe-models"
POSE_MODEL_URLS: dict[str, str] = {
    v: f"{_MODEL_ROOT}/pose_landmarker/pose_landmarker_{v}/float16/latest/pose_landmarker_{v}.task"
    for v in ("lite", "full", "heavy")
}
HAND_MODEL_URL = f"{_MODEL_ROOT}/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"


def ensure_model(url: str, models_dir: Path) -> Path:
    """Tải file .task nếu chưa có trong `models_dir`."""
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / url.rsplit("/", 1)[-1]
    if not path.exists():
        print(f"[landmarker] Đang tải model {path.name} ...")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
    return path


@dataclass
class HandDetection:
    side: str            # tay thật của người: "left" | "right" (đã đảo nhãn MediaPipe)
    score: float         # độ tin cậy phân loại handedness
    world: np.ndarray    # (21, 3) mét, gốc quanh tâm bàn tay
    image: np.ndarray    # (21, 3) tọa độ chuẩn hoá trên ảnh [0..1]


@dataclass
class RawDetection:
    timestamp: float
    pose_world: np.ndarray | None = None       # (33, 3) mét, gốc ở giữa hông
    pose_image: np.ndarray | None = None       # (33, 3) chuẩn hoá trên ảnh
    pose_visibility: np.ndarray | None = None  # (33,)
    hands: list[HandDetection] = field(default_factory=list)


def _to_array(landmarks) -> np.ndarray:
    return np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float64)


class Landmarker:
    """Chạy Pose + Hand landmarker trên cùng một frame."""

    def __init__(self, cfg: dict, models_dir: Path) -> None:
        pose_variant = cfg.get("pose_model", "full")
        pose_path = ensure_model(POSE_MODEL_URLS[pose_variant], models_dir)
        hand_path = ensure_model(HAND_MODEL_URL, models_dir)
        det = float(cfg.get("min_detection_confidence", 0.5))
        trk = float(cfg.get("min_tracking_confidence", 0.5))

        # Đọc model thành bytes (tránh lỗi đường dẫn có ký tự Unicode trên Windows)
        self._pose = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_buffer=pose_path.read_bytes()),
                running_mode=vision.RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=det,
                min_pose_presence_confidence=det,
                min_tracking_confidence=trk,
            )
        )
        # Luôn tìm tối đa 2 tay để có thể chọn đúng tay khớp với cổ tay của pose
        self._hand = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_buffer=hand_path.read_bytes()),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=det,
                min_hand_presence_confidence=det,
                min_tracking_confidence=trk,
            )
        )
        self._last_ts_ms = -1

    def detect(self, frame_bgr: np.ndarray, timestamp: float) -> RawDetection:
        """`frame_bgr` phải là ảnh KHÔNG lật gương; `timestamp` tính bằng giây (đơn điệu)."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        # Chế độ VIDEO yêu cầu timestamp (ms) tăng nghiêm ngặt
        ts_ms = max(int(timestamp * 1000), self._last_ts_ms + 1)
        self._last_ts_ms = ts_ms

        out = RawDetection(timestamp=timestamp)
        pose_res = self._pose.detect_for_video(image, ts_ms)
        if pose_res.pose_world_landmarks:
            out.pose_world = _to_array(pose_res.pose_world_landmarks[0])
            out.pose_image = _to_array(pose_res.pose_landmarks[0])
            out.pose_visibility = np.array(
                [lm.visibility if lm.visibility is not None else 0.0 for lm in pose_res.pose_landmarks[0]]
            )

        hand_res = self._hand.detect_for_video(image, ts_ms)
        for world, img, handed in zip(hand_res.hand_world_landmarks, hand_res.hand_landmarks, hand_res.handedness):
            cat = handed[0]
            # Đảo nhãn vì ảnh đầu vào không lật gương (xem docstring module)
            side = "right" if cat.category_name.lower() == "left" else "left"
            out.hands.append(HandDetection(side=side, score=float(cat.score), world=_to_array(world), image=_to_array(img)))
        return out

    def close(self) -> None:
        self._pose.close()
        self._hand.close()
