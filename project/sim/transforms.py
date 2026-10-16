"""Chuyển hệ trục MediaPipe -> PyBullet và các tiện ích quaternion.

Hệ MediaPipe (world landmarks, ảnh KHÔNG lật gương, người đứng nhìn vào camera):
    x_mp : sang PHẢI của ảnh  = sang TRÁI của người
    y_mp : xuống dưới
    z_mp : ra xa camera       = ra SAU lưng người
    (x, y, z) này là hệ thuận tay phải: x × y = z.

Hệ mô phỏng PyBullet (Z hướng lên), đặt sao cho người nhìn theo +X:
    x_sim : phía TRƯỚC mặt người  = về phía camera = -z_mp
    y_sim : bên TRÁI của người    = +x_mp
    z_sim : hướng LÊN             = -y_mp

Viết thành ma trận (mỗi HÀNG là một trục sim biểu diễn theo trục mp):

            x_mp  y_mp  z_mp
    x_sim [  0     0    -1 ]
    y_sim [  1     0     0 ]
    z_sim [  0    -1     0 ]

det(R) = +1 nên đây là phép QUAY thuần (không phản xạ): tay phải thật vẫn là tay phải
trong mô phỏng, không bị lật gương. Nhìn mô hình từ phía sau lưng sẽ thấy giống như soi gương.
"""
from __future__ import annotations

import numpy as np

R_MP_TO_SIM: np.ndarray = np.array(
    [[0.0, 0.0, -1.0],
     [1.0, 0.0, 0.0],
     [0.0, -1.0, 0.0]]
)
assert abs(np.linalg.det(R_MP_TO_SIM) - 1.0) < 1e-9


def mp_to_sim(points: np.ndarray, origin: np.ndarray | None = None, scale: float = 1.0) -> np.ndarray:
    """p_sim = origin + scale * R · p_mp  (points shape (..., 3), gốc mp = vai)."""
    out = scale * (np.asarray(points, float) @ R_MP_TO_SIM.T)
    return out if origin is None else out + np.asarray(origin, float)


def sim_to_mp(points: np.ndarray, origin: np.ndarray | None = None, scale: float = 1.0) -> np.ndarray:
    """Phép ngược của mp_to_sim (R trực giao nên R^-1 = R^T)."""
    p = np.asarray(points, float)
    if origin is not None:
        p = p - np.asarray(origin, float)
    return (p / scale) @ R_MP_TO_SIM


def quat_z_to(direction: np.ndarray) -> tuple[float, float, float, float]:
    """Quaternion (x, y, z, w) quay trục +Z cục bộ thành `direction`.

    Hình trụ/capsule của PyBullet nằm dọc trục Z cục bộ, nên quaternion này đặt xương
    dọc theo vector nối hai khớp. Dùng công thức trục-góc: trục = z × d, góc = acos(z · d).
    """
    d = np.asarray(direction, float)
    n = np.linalg.norm(d)
    if n < 1e-9:
        return 0.0, 0.0, 0.0, 1.0
    d = d / n
    dot = float(np.clip(d[2], -1.0, 1.0))  # z · d
    if dot < -0.999999:  # ngược chiều hoàn toàn: quay 180° quanh X
        return 1.0, 0.0, 0.0, 0.0
    axis = np.array([-d[1], d[0], 0.0])  # z × d
    # Dạng nửa góc ổn định số: q = (axis, 1 + dot) rồi chuẩn hoá
    q = np.array([axis[0], axis[1], axis[2], 1.0 + dot])
    q /= np.linalg.norm(q)
    return float(q[0]), float(q[1]), float(q[2]), float(q[3])
