"""TV1 local feedback stub and deterministic demo; no webcam/physics dependencies.

This is NOT evidence of real webcam or robot performance. TV4 can replace this
small local stub with dev.fakes later without changing Controller or main.run.
"""

from math import dist

from config import DEFAULT_CONFIG
from contracts import SimStatus
from control import Controller
from dev.hand_samples import make_sample


class LocalSimulation:
    def __init__(self, config=DEFAULT_CONFIG, attach_ok=True, placement_ok=True):
        self.config = config
        self.attach_ok = attach_ok
        self.placement_ok = placement_ok
        self.attach_calls = 0
        self.release_calls = 0
        self.closed = False
        self.reset()

    def initialize(self):
        return self.reset()

    def reset(self):
        self.xyz = self.config.home_xyz
        self.held = None
        self.placed = set()
        return self.status()

    def status(self):
        candidate = next((box for box, xyz, _ in self.config.boxes
                          if box not in self.placed and box != self.held
                          and dist(self.xyz[:2], xyz[:2]) < 0.04), None)
        return SimStatus(self.xyz, True, candidate, self.held, frozenset(self.placed))

    def step(self, command, dt):
        # Instant tracking of each rate-limited setpoint; no IK or physics.
        self.xyz = command.target_xyz
        return self.status()

    def try_attach(self, box_id):
        self.attach_calls += 1
        if self.held == box_id:
            return True
        pick_points = {box: (*xyz[:2], self.config.pick_z) for box, xyz, _ in self.config.boxes}
        if (self.attach_ok and self.held is None and box_id in pick_points
                and box_id not in self.placed
                and dist(self.xyz, pick_points[box_id]) <= self.config.attach_distance):
            self.held = box_id
            return True
        return False

    def release(self):
        self.release_calls += 1
        c = self.config
        inside = all(abs(p - center) <= half - c.bin_margin
                     for p, center, half in zip(self.xyz[:2], c.bin_center, c.bin_half_size))
        if self.held and inside and self.placement_ok:
            self.placed.add(self.held)
        self.held = None

    def close(self):
        self.closed = True


class Harness:
    def __init__(self, **kwargs):
        self.controller = Controller()
        self.sim = LocalSimulation(**kwargs)
        self.now = 0.0
        self.frame = 0
        self.events = []
        self.commands = []

    def tick(self, u=0.5, v=0.5, ratio=0.8, valid=True):
        self.now += 1 / 60
        self.frame += 1
        sample = make_sample(self.frame, self.now, self.now, valid, u, v, ratio)
        command = self.controller.update(sample, self.sim.status(), self.now)
        self.sim.step(command, 1 / 60)
        if command.action.value == "ATTACH":
            self.sim.try_attach(command.box_id)
        elif command.action.value == "RELEASE":
            self.sim.release()
        self.commands.append(command)
        self.events.extend(self.controller.drain_events())
        return command

    def frames(self, count, **kwargs):
        for _ in range(count):
            self.tick(**kwargs)

    def pick(self):
        # Green box: x=.5, y=-.18 maps to mirrored image u=.5, v=.752.
        self.frames(120, v=0.752)
        self.frames(180, v=0.752, ratio=0.1)

    def place(self):
        self.frames(180, v=0.248, ratio=0.1)
        self.frames(240, v=0.248, ratio=0.8)


def main():
    h = Harness()
    h.pick()
    assert h.sim.held == "green", "Pick did not confirm"
    h.place()
    assert h.sim.placed == {"green"}, "Placement did not confirm"
    assert h.sim.attach_calls == h.sim.release_calls == 1
    for event in h.events:
        print(f"{event.timestamp:5.2f}s {event.controller_state:16} {event.event_type:16} "
              f"{event.box_id or '-':5} {event.reason}")
    print("PASS: synthetic green-box pick/place; one attach, one release.")
    print("Synthetic input only; real camera, IK and physics remain unverified.")


if __name__ == "__main__":
    main()
