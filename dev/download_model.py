"""Download the official pretrained Hand Landmarker, atomically and explicitly."""
from pathlib import Path
import urllib.request

URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def main():
    target = Path(__file__).resolve().parents[1] / "models" / "hand_landmarker.task"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        print(f"Already present: {target}")
        return
    temporary = target.with_suffix(".download")
    try:
        with urllib.request.urlopen(URL, timeout=60) as response, temporary.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Downloaded: {target}")


if __name__ == "__main__":
    main()
