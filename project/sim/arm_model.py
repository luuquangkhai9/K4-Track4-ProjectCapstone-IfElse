"""Mô hình cánh tay + bàn tay trong PyBullet: hình cầu ở khớp, capsule ở xương.

Mỗi phần là một body động học (kinematic): khối lượng 0 nhưng CÓ collision shape,
được dịch chuyển mỗi frame bằng resetBasePositionAndOrientation. Vật thể động
(khối hộp trên bàn) sẽ va chạm và bị đẩy bởi tay.

Lưu ý: PyBullet không đổi được kích thước shape sau khi tạo, nên độ dài xương được
cố định. Ban đầu dùng tỉ lệ giải phẫu trung bình; sau `calib_frames` frame hợp lệ
đầu tiên thì đo độ dài thật (median) và dựng lại các xương.
"""
from __future__ import annotations

import numpy as np
import pybullet as p

from perception.fusion import BONES, HAND_OFFSET, NUM_POINTS, ArmHandFrame, canonical_points, finger_of
from sim.transforms import mp_to_sim, quat_z_to

GREY = (0.55, 0.55, 0.55, 1.0)
COLORS: dict[str, tuple[float, float, float, float]] = {
    "arm_right": (0.20, 0.50, 0.95, 1.0),
    "arm_left": (0.10, 0.75, 0.75, 1.0),
    "palm": (0.92, 0.88, 0.80, 1.0),
    "thumb": (0.95, 0.30, 0.30, 1.0),
    "index": (1.00, 0.60, 0.10, 1.0),
    "middle": (0.95, 0.90, 0.20, 1.0),
    "ring": (0.30, 0.85, 0.40, 1.0),
    "pinky": (0.70, 0.40, 0.95, 1.0),
}
# Khớp: vai, khuỷu, cổ tay + điểm bàn tay 1..20 (điểm bàn tay 0 trùng cổ tay nên bỏ qua)
JOINTS: list[int] = [0, 1, 2] + [HAND_OFFSET + i for i in range(1, 21)]
PALM_BONES = {(0, 5), (5, 9), (9, 13), (13, 17), (0, 17)}


def _joint_radius(idx: int) -> float:
    if idx < HAND_OFFSET:
        return (0.045, 0.040, 0.030)[idx]
    return 0.012 if (idx - HAND_OFFSET) % 4 == 0 else 0.013  # đầu ngón nhỏ hơn chút


def _bone_radius(a: int, b: int) -> float:
    if a < HAND_OFFSET:
        return 0.040 if a == 0 else 0.032
    return 0.011  # hơi to hơn ngón thật để dễ nhìn và dễ va chạm


class ArmModel:
    def __init__(self, client: int, side: str, origin: np.ndarray, scale: float = 1.0, calib_frames: int = 30) -> None:
        self.cid, self.side = client, side
        self.origin = np.asarray(origin, float)
        self.scale = float(scale)
        self.calib_frames = int(calib_frames)
        self._calib: list[np.ndarray] = []
        self._calibrated = self.calib_frames <= 0

        self.joint_ids: list[int] = []
        self.bone_ids: list[int] = []
        self._colors_joint = [self._part_color_joint(i) for i in JOINTS]
        self._colors_bone = [self._part_color_bone(a, b) for a, b in BONES]
        self._grey = False
        self.last_points_sim: np.ndarray | None = None

        # Kích thước mặc định từ tư thế tham chiếu, đặt mô hình ở tư thế đó (màu xám) chờ dữ liệu
        ref = canonical_points(side)
        self._lengths = self._bone_lengths(ref)
        self._build()
        self._pose(mp_to_sim(ref, self.origin, self.scale))
        self._set_grey(True)

    # ---------- màu ----------
    def _part_color_joint(self, idx: int) -> tuple[float, ...]:
        if idx < HAND_OFFSET:
            return COLORS[f"arm_{self.side}"]
        return COLORS[finger_of(idx - HAND_OFFSET)]

    def _part_color_bone(self, a: int, b: int) -> tuple[float, ...]:
        if a < HAND_OFFSET:
            return COLORS[f"arm_{self.side}"]
        ha, hb = a - HAND_OFFSET, b - HAND_OFFSET
        return COLORS["palm"] if (ha, hb) in PALM_BONES else COLORS[finger_of(hb)]

    def _set_grey(self, grey: bool) -> None:
        if grey == self._grey:
            return
        self._grey = grey
        for body, color in zip(self.joint_ids + self.bone_ids, self._colors_joint + self._colors_bone):
            p.changeVisualShape(body, -1, rgbaColor=GREY if grey else color, physicsClientId=self.cid)

    # ---------- dựng body ----------
    @staticmethod
    def _bone_lengths(pts: np.ndarray) -> np.ndarray:
        return np.array([np.linalg.norm(pts[b] - pts[a]) for a, b in BONES])

    def _remove_bodies(self) -> None:
        for body in self.joint_ids + self.bone_ids:
            p.removeBody(body, physicsClientId=self.cid)
        self.joint_ids, self.bone_ids = [], []

    def _build(self) -> None:
        self._remove_bodies()
        s, cid = self.scale, self.cid
        for idx, color in zip(JOINTS, self._colors_joint):
            r = _joint_radius(idx) * s
            col = p.createCollisionShape(p.GEOM_SPHERE, radius=r, physicsClientId=cid)
            vis = p.createVisualShape(p.GEOM_SPHERE, radius=r, rgbaColor=color, physicsClientId=cid)
            # baseMass=0 => body động học: không chịu trọng lực, chỉ di chuyển khi ta đặt lại vị trí
            self.joint_ids.append(p.createMultiBody(0, col, vis, physicsClientId=cid))
        for (a, b), length, color in zip(BONES, self._lengths, self._colors_bone):
            r = _bone_radius(a, b) * s
            h = max(float(length) * s, 1e-3)  # phần trụ dài bằng khoảng cách hai khớp, 2 đầu bo tròn nằm trong khớp
            col = p.createCollisionShape(p.GEOM_CAPSULE, radius=r, height=h, physicsClientId=cid)
            vis = p.createVisualShape(p.GEOM_CAPSULE, radius=r, length=h, rgbaColor=color, physicsClientId=cid)
            self.bone_ids.append(p.createMultiBody(0, col, vis, physicsClientId=cid))
        if self._grey:
            self._grey = False
            self._set_grey(True)

    def recalibrate(self) -> None:
        """Đo lại độ dài xương từ các frame tiếp theo (phím 'c')."""
        self._calib.clear()
        self._calibrated = False

    # ---------- cập nhật mỗi frame ----------
    def _pose(self, pts_sim: np.ndarray) -> None:
        cid = self.cid
        for body, idx in zip(self.joint_ids, JOINTS):
            p.resetBasePositionAndOrientation(body, pts_sim[idx].tolist(), (0, 0, 0, 1), physicsClientId=cid)
        for body, (a, b) in zip(self.bone_ids, BONES):
            pa, pb = pts_sim[a], pts_sim[b]
            # Capsule nằm dọc trục Z cục bộ: đặt tại trung điểm, quay Z -> vector (b - a)
            p.resetBasePositionAndOrientation(body, ((pa + pb) / 2).tolist(), quat_z_to(pb - pa), physicsClientId=cid)
        self.last_points_sim = pts_sim

    def update(self, frame: ArmHandFrame) -> None:
        if not frame.valid:
            self._set_grey(True)  # đứng yên ở tư thế cuối, đổi màu xám
            return
        pts = frame.points()
        assert pts.shape == (NUM_POINTS, 3)
        if not self._calibrated:
            self._calib.append(self._bone_lengths(pts))
            if len(self._calib) >= self.calib_frames:
                self._lengths = np.median(np.stack(self._calib), axis=0)
                self._calibrated = True
                self._build()
        self._set_grey(False)
        self._pose(mp_to_sim(pts, self.origin, self.scale))

    def remove(self) -> None:
        self._remove_bodies()
