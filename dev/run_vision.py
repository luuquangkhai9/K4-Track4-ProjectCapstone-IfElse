"""TV2 standalone webcam/overlay runner; no controller or simulator required."""

import argparse
from dataclasses import replace
import time

from config import DEFAULT_CONFIG
from vision import Vision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="0", help="Webcam index or video path")
    parser.add_argument("--hand", choices=("Right", "Left"), default="Right")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--no-overlay", action="store_true")
    args = parser.parse_args()
    if args.duration is not None and args.duration <= 0:
        parser.error("--duration must be positive")
    config = replace(DEFAULT_CONFIG, hand_side=args.hand,
                     camera_source=int(args.source) if args.source.isdigit() else args.source)
    vision = Vision(config)
    cv2 = None
    try:
        vision.start()
        started = time.monotonic()
        last_id = None
        while args.duration is None or time.monotonic() - started < args.duration:
            sample = vision.latest_sample()
            if sample is not None and sample.frame_id != last_id:
                print(sample)
                last_id = sample.frame_id
            frame = vision.latest_overlay()
            if frame is not None and not args.no_overlay:
                if cv2 is None:
                    import cv2
                cv2.imshow("TV2 hand tracking", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
            if vision.error:
                raise RuntimeError(vision.error)
            time.sleep(1 / config.loop_hz)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            vision.close()
        finally:
            if cv2 is not None:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
