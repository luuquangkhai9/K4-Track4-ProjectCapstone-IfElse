"""Hiển thị bộ xương 3D bằng matplotlib (chế độ --debug-3d, không cần PyBullet).

Vẽ trong hệ trục mô phỏng (Z lên, người nhìn theo +X) để dễ hình dung,
gốc tại vai, đơn vị mét.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from perception.fusion import BONES, HAND_OFFSET, ArmHandFrame, finger_of
from sim.transforms import mp_to_sim

BONE_COLORS = {"arm": "#3b82f6", "palm": "#9ca3af", "thumb": "#ef4444", "index": "#f97316",
               "middle": "#eab308", "ring": "#22c55e", "pinky": "#a855f7"}


def bone_part(a: int, b: int) -> str:
    if a < HAND_OFFSET:
        return "arm"
    ha, hb = a - HAND_OFFSET, b - HAND_OFFSET
    return "palm" if (ha, hb) in {(0, 5), (5, 9), (9, 13), (13, 17), (0, 17)} else finger_of(hb)


class Skeleton3DViewer:
    def __init__(self, sides: list[str], limit: float = 0.8) -> None:
        plt.ion()
        self.fig = plt.figure("Arm/Hand 3D debug", figsize=(7, 7))
        self.ax = self.fig.add_subplot(111, projection="3d")
        ax = self.ax
        ax.set_xlim(-0.3, limit)
        ax.set_ylim(-limit / 2 - 0.3, limit / 2 + 0.3)
        ax.set_zlim(-limit, 0.3)
        ax.set_xlabel("X trước (m)")
        ax.set_ylabel("Y trái (m)")
        ax.set_zlabel("Z lên (m)")
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=15, azim=-150)  # nhìn chéo từ phía sau-phải người
        ax.scatter([0], [0], [0], c="k", s=30)  # gốc = vai
        self.lines: dict[str, list] = {}
        self.dots: dict[str, object] = {}
        for s in sides:
            self.lines[s] = [ax.plot([], [], [], color=BONE_COLORS[bone_part(a, b)],
                                     lw=5 if bone_part(a, b) == "arm" else 3)[0] for a, b in BONES]
            self.dots[s] = ax.plot([], [], [], "o", color="#374151", ms=2)[0]
        self.title = ax.set_title("")
        self._closed = False
        self.fig.canvas.mpl_connect("close_event", lambda _e: setattr(self, "_closed", True))

    @property
    def is_open(self) -> bool:
        return not self._closed

    def update(self, frames: dict[str, ArmHandFrame], fps: float) -> None:
        texts = []
        for s, f in frames.items():
            if s not in self.lines:
                continue
            pts = mp_to_sim(f.points())
            for line, (a, b) in zip(self.lines[s], BONES):
                line.set_data_3d(pts[[a, b], 0], pts[[a, b], 1], pts[[a, b], 2])
                line.set_alpha(1.0 if f.valid else 0.25)
            self.dots[s].set_data_3d(pts[:, 0], pts[:, 1], pts[:, 2])
            w, tip = pts[2], pts[HAND_OFFSET + 8]
            texts.append(f"{s}: {'valid' if f.valid else 'INVALID'} conf={f.confidence:.2f} "
                         f"wrist={np.round(w, 2)} index={np.round(tip, 2)}")
        self.title.set_text(f"FPS {fps:.1f}\n" + "\n".join(texts))

    def pause(self, seconds: float = 0.001) -> None:
        plt.pause(seconds)

    def close(self) -> None:
        plt.close(self.fig)
