"""One Euro Filter (Casiez et al., CHI 2012) - cài đặt vector hoá cho mảng numpy.

Ý tưởng: bộ lọc thông thấp có tần số cắt thay đổi theo tốc độ.
- Khi tay gần như đứng yên -> tần số cắt thấp (min_cutoff) -> lọc mạnh, hết rung.
- Khi tay chuyển động nhanh -> tần số cắt tăng (beta * |vận tốc|) -> ít trễ.
"""
from __future__ import annotations

import math

import numpy as np


def _alpha(dt: float, cutoff: np.ndarray | float) -> np.ndarray | float:
    """Hệ số làm mượt của bộ lọc mũ bậc 1 ứng với tần số cắt `cutoff` (Hz)."""
    tau = 1.0 / (2.0 * math.pi * np.asarray(cutoff))
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    """Lọc một mảng giá trị bất kỳ shape (mỗi phần tử được lọc độc lập).

    Đơn vị: vị trí tính bằng mét, vận tốc m/s, nên `beta` có đơn vị s/m.
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 4.0, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.reset()

    def reset(self) -> None:
        self._x_prev: np.ndarray | None = None
        self._dx_prev: np.ndarray | None = None
        self._t_prev: float | None = None

    def __call__(self, x: np.ndarray, t: float) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        if self._x_prev is None or self._t_prev is None or self._x_prev.shape != x.shape:
            self._x_prev = x.copy()
            self._dx_prev = np.zeros_like(x)
            self._t_prev = t
            return x.copy()

        dt = t - self._t_prev
        if dt <= 1e-6:  # timestamp trùng hoặc lùi -> giả định 1 ms để tránh chia 0
            dt = 1e-3

        # 1) Ước lượng vận tốc rồi làm mượt vận tốc với tần số cắt cố định d_cutoff
        dx = (x - self._x_prev) / dt
        a_d = _alpha(dt, self.d_cutoff)
        dx_hat = a_d * dx + (1.0 - a_d) * self._dx_prev

        # 2) Tần số cắt thích nghi theo tốc độ, rồi lọc vị trí
        cutoff = self.min_cutoff + self.beta * np.abs(dx_hat)
        a = _alpha(dt, cutoff)
        x_hat = a * x + (1.0 - a) * self._x_prev

        self._x_prev, self._dx_prev, self._t_prev = x_hat, dx_hat, t
        return x_hat.copy()
