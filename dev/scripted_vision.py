"""Explicit synthetic hand input for physics/integration checks, not live evidence."""
import time
from config import DEFAULT_CONFIG
from dev.hand_samples import make_sample


class Vision:
    def __init__(self, config=DEFAULT_CONFIG):
        self.config = config
        self.frame = 0
        self.is_synthetic = True

    def start(self):
        self.started = time.monotonic()

    def latest_sample(self):
        now = time.monotonic()
        elapsed = now - self.started
        self.frame += 1
        return make_sample(self.frame, now, now, True, .5,
                          .752 if elapsed < 5 else .248,
                          .8 if elapsed < 2 or elapsed >= 8 else .1,
                          side=self.config.hand_side)

    def close(self):
        pass
