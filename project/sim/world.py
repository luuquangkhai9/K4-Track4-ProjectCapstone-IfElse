"""Cảnh PyBullet: mặt đất, bàn, khối hộp nhỏ, camera, text debug + ArmScene ghép mô hình tay.

Phím trong cửa sổ PyBullet:
    r : đặt lại các khối hộp      c : đo lại độ dài xương      q / ESC : thoát
"""
from __future__ import annotations

import time

import numpy as np
import pybullet as p
import pybullet_data

from perception.fusion import HAND_OFFSET, ArmHandFrame
from sim.arm_model import ArmModel

BOX_COLORS = [(0.9, 0.2, 0.2, 1), (0.2, 0.7, 0.3, 1), (0.2, 0.4, 0.9, 1), (0.95, 0.75, 0.1, 1)]


class SimWorld:
    def __init__(self, cfg: dict, gui: bool = True) -> None:
        self.cfg = cfg
        self.gui = gui
        self.cid = p.connect(p.GUI if gui else p.DIRECT)
        cid = self.cid
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=cid)
        p.setGravity(0, 0, -9.81, physicsClientId=cid)
        self.dt = 1.0 / float(cfg.get("physics_hz", 240))
        p.setTimeStep(self.dt, physicsClientId=cid)
        if gui:
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0, physicsClientId=cid)  # ẩn panel bên
            p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1, physicsClientId=cid)
        cam = cfg.get("camera", {})
        self.camera = dict(distance=float(cam.get("distance", 1.6)), yaw=float(cam.get("yaw", -90)),
                           pitch=float(cam.get("pitch", -25)), target=list(cam.get("target", [0.35, 0, 1.05])))
        p.resetDebugVisualizerCamera(self.camera["distance"], self.camera["yaw"], self.camera["pitch"],
                                     self.camera["target"], physicsClientId=cid)

        p.loadURDF("plane.urdf", physicsClientId=cid)
        self._build_table()
        self.box_ids: list[int] = []
        self.reset_boxes()
        self._text_ids: dict[str, int] = {}

    # ---------- dựng cảnh ----------
    def _static_box(self, half: list[float], pos: list[float], color: tuple) -> int:
        col = p.createCollisionShape(p.GEOM_BOX, halfExtents=half, physicsClientId=self.cid)
        vis = p.createVisualShape(p.GEOM_BOX, halfExtents=half, rgbaColor=color, physicsClientId=self.cid)
        return p.createMultiBody(0, col, vis, basePosition=pos, physicsClientId=self.cid)

    def _build_table(self) -> None:
        t = self.cfg.get("table", {})
        cx, cy = t.get("center", [0.5, 0.0])
        sx, sy = t.get("size", [0.6, 1.0])
        h = float(t.get("height", 0.85))
        top = 0.03
        self.table_top_z = h
        wood, leg = (0.62, 0.45, 0.30, 1), (0.35, 0.25, 0.18, 1)
        self._static_box([sx / 2, sy / 2, top / 2], [cx, cy, h - top / 2], wood)
        for dx in (-1, 1):
            for dy in (-1, 1):
                self._static_box([0.025, 0.025, (h - top) / 2],
                                 [cx + dx * (sx / 2 - 0.04), cy + dy * (sy / 2 - 0.04), (h - top) / 2], leg)

    def reset_boxes(self) -> None:
        for b in self.box_ids:
            p.removeBody(b, physicsClientId=self.cid)
        self.box_ids = []
        for i, (x, y, size) in enumerate(self.cfg.get("boxes", [])):
            half = [size / 2] * 3
            col = p.createCollisionShape(p.GEOM_BOX, halfExtents=half, physicsClientId=self.cid)
            vis = p.createVisualShape(p.GEOM_BOX, halfExtents=half, rgbaColor=BOX_COLORS[i % len(BOX_COLORS)],
                                      physicsClientId=self.cid)
            body = p.createMultiBody(0.05, col, vis, basePosition=[x, y, self.table_top_z + size / 2 + 0.001],
                                     physicsClientId=self.cid)
            p.changeDynamics(body, -1, lateralFriction=0.8, physicsClientId=self.cid)
            self.box_ids.append(body)

    # ---------- tiện ích ----------
    def set_text(self, key: str, text: str, pos: list[float], color: tuple = (0, 0, 0), size: float = 1.2) -> None:
        """Cập nhật text debug tại chỗ (replaceItemUniqueId) thay vì tạo mới mỗi frame."""
        kwargs = {"replaceItemUniqueId": self._text_ids[key]} if key in self._text_ids else {}
        self._text_ids[key] = p.addUserDebugText(text, pos, textColorRGB=color, textSize=size,
                                                 physicsClientId=self.cid, **kwargs)

    def step(self, n: int = 1) -> None:
        for _ in range(n):
            p.stepSimulation(physicsClientId=self.cid)

    def is_connected(self) -> bool:
        return p.isConnected(self.cid)

    def keys(self) -> dict[int, int]:
        return p.getKeyboardEvents(physicsClientId=self.cid) if self.gui else {}

    def screenshot(self, width: int = 960, height: int = 720) -> np.ndarray:
        c = self.camera
        view = p.computeViewMatrixFromYawPitchRoll(c["target"], c["distance"], c["yaw"], c["pitch"], 0, 2)
        proj = p.computeProjectionMatrixFOV(60, width / height, 0.05, 20)
        img = p.getCameraImage(width, height, view, proj, physicsClientId=self.cid)[2]
        return np.reshape(img, (height, width, 4))[:, :, :3].astype(np.uint8)

    def close(self) -> None:
        if p.isConnected(self.cid):
            p.disconnect(self.cid)


class ArmScene:
    """Cảnh + một mô hình cánh tay cho mỗi tay được theo dõi."""

    def __init__(self, cfg: dict, sides: list[str], gui: bool = True) -> None:
        self.world = SimWorld(cfg, gui=gui)
        self.origin = np.asarray(cfg.get("origin", [0.0, 0.0, 1.4]), float)
        scale = float(cfg.get("scale", 1.0))
        self.arms = {s: ArmModel(self.world.cid, s, self.origin, scale, int(cfg.get("calib_frames", 30)))
                     for s in sides}
        self.substeps = max(1, round(float(cfg.get("physics_hz", 240)) / float(cfg.get("rate", 60))))
        self._last_text = 0.0
        self._last_frames: dict[str, ArmHandFrame] = {}
        self._fps = 0.0
        # Đánh dấu vị trí gốc (vai) bằng hệ trục nhỏ: đỏ = X trước, xanh lá = Y trái, xanh dương = Z lên
        for axis, color in zip(np.eye(3), np.eye(3)):
            p.addUserDebugLine(self.origin.tolist(), (self.origin + 0.1 * axis).tolist(), color.tolist(), 2,
                               physicsClientId=self.world.cid)

    def update(self, frames: dict[str, ArmHandFrame], fps: float) -> None:
        for s, f in frames.items():
            if s in self.arms:
                self.arms[s].update(f)
        self._last_frames, self._fps = frames, fps

    def _update_texts(self) -> None:
        now = time.monotonic()
        if now - self._last_text < 0.1:  # 10 Hz là đủ, addUserDebugText khá tốn
            return
        self._last_text = now
        base = self.origin + np.array([0.0, 0.0, 0.42])
        lines = [f"Perception FPS: {self._fps:5.1f}"]
        for s, f in self._last_frames.items():
            # Tọa độ hiển thị: hệ sim, tương đối vai (m) - X trước, Y trái, Z lên
            arm = self.arms.get(s)
            if arm is None or arm.last_points_sim is None:
                continue
            rel = (arm.last_points_sim - self.origin)
            w, tip = rel[2], rel[HAND_OFFSET + 8]
            lines.append(f"[{s}] {'VALID' if f.valid else 'INVALID (lost)'}  conf={f.confidence:.2f}")
            lines.append(f"  wrist  ({w[0]:+.3f}, {w[1]:+.3f}, {w[2]:+.3f})")
            lines.append(f"  index  ({tip[0]:+.3f}, {tip[1]:+.3f}, {tip[2]:+.3f})")
        all_valid = all(f.valid for f in self._last_frames.values()) if self._last_frames else False
        for i, line in enumerate(lines):
            color = (0.1, 0.1, 0.1) if i == 0 else ((0.0, 0.45, 0.0) if all_valid else (0.7, 0.0, 0.0))
            self.world.set_text(f"line{i}", line, (base - np.array([0, 0, 0.055 * i])).tolist(), color)
        for i in range(len(lines), 8):  # xoá dòng thừa
            self.world.set_text(f"line{i}", "", base.tolist())

    def step_and_handle_keys(self) -> bool:
        """Bước vật lý + xử lý phím. Trả về False nếu người dùng muốn thoát."""
        self.world.step(self.substeps)
        self._update_texts()
        for key, state in self.world.keys().items():
            if not state & p.KEY_WAS_TRIGGERED:
                continue
            if key in (ord("q"), 27):
                return False
            if key == ord("r"):
                self.world.reset_boxes()
            if key == ord("c"):
                for arm in self.arms.values():
                    arm.recalibrate()
        return True

    def is_connected(self) -> bool:
        return self.world.is_connected()

    def save_screenshot(self, path: str) -> None:
        import cv2
        cv2.imwrite(path, cv2.cvtColor(self.world.screenshot(), cv2.COLOR_RGB2BGR))
        print(f"[sim] Đã lưu ảnh cảnh vào {path}")

    def close(self) -> None:
        self.world.close()
