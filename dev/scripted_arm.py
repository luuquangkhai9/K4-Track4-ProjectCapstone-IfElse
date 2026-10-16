"""Synthetic moving arm for the REAL robot simulation; explicitly labeled demo."""
from math import sin, cos
import time
from contracts import ArmSample


class Vision:
    is_synthetic = True
    def __init__(self, config=None):
        self.frame = 0
        self._started_calibration = False

    def start(self):
        self.started = time.monotonic()

    def poll_key(self):
        if not self._started_calibration and time.monotonic()-self.started > .2:
            self._started_calibration = True
            return "c"

    def latest_sample(self):
        self.frame += 1
        now = time.monotonic()
        t = max(0, now-self.started-1.5)
        return ArmSample(self.frame, now, now, True, (0,0,0),
                         (.12+.05*sin(t), .18-.08*sin(t), -.05-.03*sin(t)),
                         (.18+.10*sin(t), .25-.10*sin(t), -.25-.08*sin(t*.7)))

    def close(self):
        pass
