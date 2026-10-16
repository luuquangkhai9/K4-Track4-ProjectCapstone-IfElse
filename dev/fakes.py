"""TV4 scripted doubles, never evidence of real tracking/physics.

Use the integrated contracts and raw arm/hand fixtures from TV1.
"""
from __future__ import annotations

from time import monotonic

from contracts import HandSample, RobotCommand, SimStatus, TrialRecord
from dev.hand_samples import make_sample

USING_SHARED_CONTRACTS = True


def hand_sample(*, frame_id=0, now=None, valid=True, u=0.5, v=0.5, pinch_ratio=0.8, side="Right"):
    timestamp = monotonic() if now is None else now
    return make_sample(frame_id, timestamp, timestamp, valid, u, v, pinch_ratio, side=side)


def sim_status(*, ee_xyz=(0.5, 0.0, 0.4), target_reached=True,
               candidate_box_id=None, held_box_id=None, placed_box_ids=()):
    return SimStatus(ee_xyz=ee_xyz, target_reached=target_reached,
                     candidate_box_id=candidate_box_id, held_box_id=held_box_id,
                     placed_box_ids=frozenset(placed_box_ids))


class FakeVision:
    """Explicitly advance samples; repeated latest_sample() never consumes input."""

    def __init__(self, samples=None):
        self.samples = list(samples) if samples is not None else [hand_sample()]
        if not self.samples:
            raise ValueError("Supply at least one HandSample")
        self.index = 0
        self.started = False

    def start(self):
        self.index = 0
        self.started = True

    def latest_sample(self):
        if not self.started:
            raise RuntimeError("Call start() first")
        return self.samples[self.index]

    def advance(self):
        self.index = min(self.index + 1, len(self.samples) - 1)
        return self.latest_sample()

    def close(self):
        self.started = False


class FakeSimulator:
    """Responses supplied by the test author, not a second physics simulator.

    step() records a command and consumes one scripted status, then holds the
    last status. ATTACH/RELEASE never invent successful feedback. Supply the
    corresponding held/placed status explicitly in the next script entry.
    """

    def __init__(self, statuses=None, *, attach_results=None):
        self.statuses = list(statuses) if statuses is not None else [sim_status()]
        if not self.statuses:
            raise ValueError("Supply at least one SimStatus")
        self.attach_results = dict(attach_results or {})
        self.commands = []
        self.actions = []
        self.index = 0
        self.initialized = False

    def initialize(self):
        self.reset()
        self.initialized = True
        return self.statuses[0]

    def step(self, command, dt):
        if not self.initialized:
            raise RuntimeError("Call initialize() first")
        if dt < 0:
            raise ValueError("dt must be nonnegative")
        if dt == 0:
            return self.statuses[self.index]
        self.commands.append(command)
        status = self.statuses[self.index]
        self.index = min(self.index + 1, len(self.statuses) - 1)
        return status

    def try_attach(self, box_id):
        if not self.initialized:
            raise RuntimeError("Call initialize() first")
        self.actions.append(("ATTACH", box_id))
        return self.attach_results.get(box_id, False)

    def release(self):
        if not self.initialized:
            raise RuntimeError("Call initialize() first")
        self.actions.append(("RELEASE", None))

    def reset(self):
        self.index = 0
        self.commands.clear()
        self.actions.clear()
        return self.statuses[0]

    def close(self):
        self.initialized = False
