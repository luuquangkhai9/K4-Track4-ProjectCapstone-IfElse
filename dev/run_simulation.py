"""TV3 scripted pick/place using real PyBullet; no webcam or vision dependency."""

import argparse
from dataclasses import replace
from math import dist
import time

from config import DEFAULT_CONFIG
from contracts import RobotCommand
from simulation import Simulation


def run_sequence(simulation, config, box_id, realtime=True):
    """Use rate-limited waypoints and physical feedback, fail on unreachable poses."""
    status = simulation.initialize()
    dt = 1 / config.loop_hz
    target = status.ee_xyz

    def move(goal, closed):
        nonlocal status, target
        for _ in range(int(config.motion_timeout_s / dt)):
            distance = dist(target, goal)
            fraction = min(1, config.max_speed * dt / distance) if distance else 1
            target = tuple(a + fraction*(b-a) for a, b in zip(target, goal))
            status = simulation.step(RobotCommand(target, closed), dt)
            if realtime:
                time.sleep(dt)
            if dist(target, goal) < 1e-6 and status.target_reached:
                return
        raise RuntimeError(f"Robot did not reach {goal}: {status.ee_xyz}")

    pick = next(xyz for name, xyz, _ in config.boxes if name == box_id)
    move((*pick[:2], config.transport_z), False)
    move((*pick[:2], config.pick_z), False)
    simulation.try_attach(box_id)
    status = simulation.step(RobotCommand(target, True), dt)
    if status.held_box_id != box_id:
        raise RuntimeError(f"Attachment not confirmed for {box_id}")
    print(f"PICKED {box_id}")
    move((*pick[:2], config.transport_z), True)
    move((*config.bin_center, config.transport_z), True)
    move((*config.bin_center, config.place_z), True)
    simulation.release()
    for _ in range(int((config.action_timeout_s + config.placement_settle_s) / dt)):
        status = simulation.step(RobotCommand(target, False), dt)
        if realtime:
            time.sleep(dt)
        if box_id in status.placed_box_ids:
            break
    if status.held_box_id is not None or box_id not in status.placed_box_ids:
        raise RuntimeError(f"Placement not confirmed for {box_id}")
    move((*config.bin_center, config.transport_z), False)
    print(f"PASS: {box_id} released and settled inside bin (real PyBullet, scripted input)")
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--box", choices=[box[0] for box in DEFAULT_CONFIG.boxes], default="green")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    config = replace(DEFAULT_CONFIG, simulation_gui=not args.headless)
    simulation = Simulation(config)
    try:
        run_sequence(simulation, config, args.box, realtime=not args.headless)
    finally:
        simulation.close()


if __name__ == "__main__":
    main()
