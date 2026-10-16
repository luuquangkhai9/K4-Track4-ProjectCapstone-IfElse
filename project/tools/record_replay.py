"""Ghi / phát lại chuỗi ArmHandFrame (.npz) và sinh dữ liệu giả để thử mô phỏng không cần webcam.

Định dạng .npz:
    sides            : mảng tên tay, ví dụ ["right"]
    t                : (N,) timestamp (giây, bắt đầu từ 0)
    <side>_points    : (N, 24, 3) tọa độ hệ MediaPipe, gốc ở vai (mét)
    <side>_conf      : (N,)
    <side>_valid     : (N,) bool

Dùng làm script:
    python -m tools.record_replay --synthetic demo.npz [--seconds 20] [--hands right|left|both]
    python -m tools.record_replay --info demo.npz
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

import numpy as np

from perception.fusion import ArmHandFrame, build_arm_points, parse_sides
from perception.pipeline import LatestBuffer, PerceptionOutput
from sim.transforms import sim_to_mp


class Recorder:
    """Gom các frame (mỗi lần perception có kết quả mới) rồi lưu ra .npz."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._frames: list[dict[str, ArmHandFrame]] = []

    def add(self, frames: dict[str, ArmHandFrame]) -> None:
        self._frames.append(frames)

    def __len__(self) -> int:
        return len(self._frames)

    def save(self) -> Path | None:
        if not self._frames:
            print("[record] Không có frame nào để lưu.")
            return None
        save_frames(self.path, self._frames)
        print(f"[record] Đã lưu {len(self._frames)} frame vào {self.path}")
        return self.path


def save_frames(path: str | Path, frames: list[dict[str, ArmHandFrame]]) -> None:
    sides = sorted(frames[0].keys())
    t0 = next(iter(frames[0].values())).timestamp
    data: dict[str, np.ndarray] = {
        "sides": np.array(sides),
        "t": np.array([next(iter(f.values())).timestamp - t0 for f in frames]),
    }
    for s in sides:
        data[f"{s}_points"] = np.stack([f[s].points() for f in frames]).astype(np.float32)
        data[f"{s}_conf"] = np.array([f[s].confidence for f in frames], dtype=np.float32)
        data[f"{s}_valid"] = np.array([f[s].valid for f in frames], dtype=bool)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **data)


def load_frames(path: str | Path) -> tuple[np.ndarray, list[dict[str, ArmHandFrame]]]:
    d = np.load(path)
    sides = [str(s) for s in d["sides"]]
    t = d["t"].astype(np.float64)
    frames = [
        {s: ArmHandFrame.from_points(d[f"{s}_points"][i], float(t[i]), float(d[f"{s}_conf"][i]),
                                     bool(d[f"{s}_valid"][i]), s) for s in sides}
        for i in range(len(t))
    ]
    return t, frames


class ReplayThread(threading.Thread):
    """Phát lại file .npz vào cùng LatestBuffer như perception thật, giữ đúng nhịp thời gian gốc."""

    def __init__(self, path: str | Path, buffer: LatestBuffer[PerceptionOutput], loop: bool = True) -> None:
        super().__init__(name="replay", daemon=True)
        self.t, self.frames = load_frames(path)
        self.buffer, self.loop = buffer, loop
        self._stop_event = threading.Event()
        self.error: BaseException | None = None
        self.ready = threading.Event()
        self.ready.set()
        self.finished = threading.Event()
        dur = float(self.t[-1] - self.t[0]) if len(self.t) > 1 else 0.0
        self.fps = (len(self.t) - 1) / dur if dur > 0 else 0.0

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            start = time.monotonic()
            for ti, frames in zip(self.t, self.frames):
                wait = start + float(ti) - time.monotonic()
                if wait > 0 and self._stop_event.wait(wait):
                    return
                now = time.monotonic()
                # Gắn timestamp hiện tại để phía mô phỏng xử lý như dữ liệu live
                live = {s: ArmHandFrame.from_points(f.points(), now, f.confidence, f.valid, s) for s, f in frames.items()}
                self.buffer.put(PerceptionOutput(frames=live, fps=self.fps))
            if not self.loop:
                break
        self.finished.set()


def synthetic_frames(seconds: float = 20.0, rate: float = 30.0, hands: str = "right") -> list[dict[str, ArmHandFrame]]:
    """Sinh chuyển động giả: với tay ra trước, hạ xuống chạm mặt bàn, nắm/mở bàn tay.

    Có chèn một đoạn mất dấu (valid=False) để thử trạng thái màu xám.
    Chuyển động được tạo trong hệ sim (dễ nghĩ hơn) rồi đổi về hệ MediaPipe.
    """
    sides = parse_sides(hands)
    frames: list[dict[str, ArmHandFrame]] = []
    n = int(seconds * rate)
    for i in range(n):
        t = i / rate
        w = 2 * np.pi / 6.0  # chu kỳ 6 s
        out: dict[str, ArmHandFrame] = {}
        for s in sides:
            sign = 1.0 if s == "left" else -1.0  # bên trái người là +Y trong hệ sim
            upper = np.array([0.35 + 0.25 * np.sin(w * t), sign * 0.15, -1.0])
            fore = np.array([1.0, sign * 0.25 * np.sin(0.7 * w * t), -0.35 - 0.55 * (0.5 + 0.5 * np.sin(w * t + 1.0))])
            curl = 0.75 * (0.5 + 0.5 * np.sin(1.3 * w * t))
            pts_sim = build_arm_points(s, upper, fore, palm_normal=np.array([0.0, 0.0, -1.0]), curl=curl)
            if len(sides) == 2:
                pts_sim += np.array([0.0, sign * 0.18, 0.0])  # gốc ở giữa hai vai
            valid = not (0.6 * seconds <= t < 0.6 * seconds + 1.5)  # 1.5 s "mất dấu"
            out[s] = ArmHandFrame.from_points(sim_to_mp(pts_sim), t, 0.9 if valid else 0.0, valid, s)
        frames.append(out)
    return frames


def main() -> None:
    # Console Windows mặc định cp1252 không in được tiếng Việt
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--synthetic", metavar="OUT.npz", help="sinh dữ liệu giả và lưu ra file")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--hands", default="right", choices=["left", "right", "both"])
    ap.add_argument("--info", metavar="FILE.npz", help="in thông tin một file ghi")
    args = ap.parse_args()
    if args.synthetic:
        frames = synthetic_frames(args.seconds, hands=args.hands)
        save_frames(args.synthetic, frames)
        print(f"Đã ghi {len(frames)} frame giả vào {args.synthetic}")
    if args.info:
        t, frames = load_frames(args.info)
        sides = list(frames[0].keys())
        print(f"{args.info}: {len(t)} frame, {t[-1]:.1f} s, tay={sides}")
        for s in sides:
            valid = np.mean([f[s].valid for f in frames])
            print(f"  {s}: valid {valid * 100:.0f}%  vai->cổ tay TB = "
                  f"{np.mean([np.linalg.norm(f[s].wrist - f[s].shoulder) for f in frames]):.3f} m")
    if not (args.synthetic or args.info):
        ap.print_help()


if __name__ == "__main__":
    main()
