"""Nhận diện cánh tay + bàn tay 3D qua webcam và tái hiện trong PyBullet theo thời gian thực.

Ví dụ:
    python main.py                          # webcam -> PyBullet (real-time)
    python main.py --debug-3d               # chỉ perception + bộ xương 3D (matplotlib)
    python main.py --print                  # in tọa độ 3D ra console
    python main.py --record clip.npz        # chạy bình thường và ghi lại chuỗi frame
    python main.py --replay clip.npz        # phát lại vào PyBullet, không cần webcam
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from perception.fusion import ArmHandFrame, parse_sides  # noqa: E402
from perception.pipeline import CameraPerceptionThread, LatestBuffer, PerceptionOutput  # noqa: E402
from tools.record_replay import Recorder, ReplayThread  # noqa: E402

POINT_NAMES = ["shoulder", "elbow", "wrist"] + [f"hand{i:02d}" for i in range(21)]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--debug-3d", action="store_true", help="chỉ perception + matplotlib 3D, không mở PyBullet")
    ap.add_argument("--print", dest="print_coords", action="store_true", help="in tọa độ 3D ra console")
    ap.add_argument("--sim", action="store_true", help="vẫn mở PyBullet khi dùng --print")
    ap.add_argument("--record", metavar="FILE.npz", help="ghi chuỗi frame 3D ra file")
    ap.add_argument("--replay", metavar="FILE.npz", help="phát lại file thay cho webcam")
    ap.add_argument("--no-loop", action="store_true", help="phát lại một lần rồi thoát")
    ap.add_argument("--hands", choices=["left", "right", "both"], help="ghi đè perception.hands")
    ap.add_argument("--duration", type=float, default=0.0, help="tự thoát sau N giây (0 = chạy mãi)")
    ap.add_argument("--headless", action="store_true", help="PyBullet DIRECT, không mở cửa sổ (để test)")
    ap.add_argument("--screenshot", metavar="FILE.png", help="lưu ảnh render cảnh PyBullet khi thoát")
    return ap.parse_args()


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def format_frame(f: ArmHandFrame) -> str:
    pts = np.round(f.points(), 3)
    head = f"[{f.side}] t={f.timestamp:.3f} valid={f.valid} conf={f.confidence:.2f}"
    body = "  ".join(f"{name}=({p[0]:+.3f},{p[1]:+.3f},{p[2]:+.3f})" for name, p in zip(POINT_NAMES, pts))
    return f"{head}\n  {body}"


def main() -> int:
    # Console Windows mặc định cp1252 không in được tiếng Việt
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    cfg = load_config(args.config)
    if args.hands:
        cfg.setdefault("perception", {})["hands"] = args.hands
    show_camera = bool(cfg.get("display", {}).get("show_camera", True)) and not args.replay
    run_sim = not (args.debug_3d or args.print_coords) or args.sim

    # --- Nguồn dữ liệu: webcam (luồng perception) hoặc file replay ---
    buffer: LatestBuffer[PerceptionOutput] = LatestBuffer()
    if args.replay:
        source = ReplayThread(args.replay, buffer, loop=not args.no_loop)
        sides = list(source.frames[0].keys())
    else:
        source = CameraPerceptionThread(cfg, buffer, ROOT / "models")
        sides = parse_sides(cfg.get("perception", {}).get("hands", "right"))
    source.start()
    print("[main] Đang khởi động nguồn dữ liệu (lần đầu sẽ tải model MediaPipe)...")
    source.ready.wait()
    if source.error:
        print(f"[main] Lỗi nguồn dữ liệu: {source.error!r}")
        return 1

    recorder = Recorder(args.record) if args.record else None
    viewer = None
    scene = None
    if args.debug_3d:
        from tools.debug_3d import Skeleton3DViewer
        viewer = Skeleton3DViewer(sides)
    if run_sim:
        from sim.world import ArmScene
        scene = ArmScene(cfg.get("sim", {}), sides, gui=not args.headless)

    sim_rate = float(cfg.get("sim", {}).get("rate", 60))
    print_period = 1.0 / float(cfg.get("record", {}).get("print_hz", 5))
    last_seq, last_print = 0, 0.0
    t_start = time.monotonic()
    print("[main] Đang chạy. Nhấn 'q' hoặc ESC trên cửa sổ camera (hoặc đóng cửa sổ) để thoát.")

    try:
        while True:
            loop_start = time.monotonic()
            if source.error:
                print(f"[main] Lỗi nguồn dữ liệu: {source.error!r}")
                break
            if args.duration and loop_start - t_start > args.duration:
                break
            if isinstance(source, ReplayThread) and source.finished.is_set():
                break

            seq, out = buffer.get()
            new = out is not None and seq != last_seq
            if new:
                last_seq = seq
                if recorder is not None:
                    recorder.add(out.frames)
                if args.print_coords and loop_start - last_print >= print_period:
                    last_print = loop_start
                    print(f"--- FPS {out.fps:.1f}")
                    for f in out.frames.values():
                        print(format_frame(f))

            # --- Hiển thị ---
            key = -1
            if show_camera and out is not None and out.image is not None:
                if new:
                    cv2.imshow("Webcam - keypoints", out.image)
                key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if viewer is not None:
                if not viewer.is_open:
                    break
                if new:
                    viewer.update(out.frames, out.fps)
                viewer.pause(0.001)
            if scene is not None:
                if not scene.is_connected():
                    break
                if new:
                    scene.update(out.frames, out.fps)
                if not scene.step_and_handle_keys():
                    break
                # Giữ nhịp vòng lặp mô phỏng ~ sim.rate Hz
                remain = 1.0 / sim_rate - (time.monotonic() - loop_start)
                if remain > 0:
                    time.sleep(remain)
            elif viewer is None:
                time.sleep(0.005)  # chỉ in/ghi: tránh vòng lặp bận
    except KeyboardInterrupt:
        pass
    finally:
        source.stop()
        source.join(timeout=2.0)
        if recorder is not None:
            recorder.save()
        if scene is not None:
            if args.screenshot:
                scene.save_screenshot(args.screenshot)
            scene.close()
        if viewer is not None:
            viewer.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
