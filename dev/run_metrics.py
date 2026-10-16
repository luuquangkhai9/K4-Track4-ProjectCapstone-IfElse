"""TV4 entry point. Default: verify and report explicitly synthetic data."""
from __future__ import annotations

import argparse
import csv
import importlib
import importlib.metadata
import json
import platform
import sys
import tempfile
import unittest
from pathlib import Path
from time import monotonic_ns

from metrics import MetricsLogger, read_trials, summarize, write_report

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).resolve().parent / "sample_data"


def run_report(args):
    source = Path(args.input).resolve() if args.input else SAMPLES / "trials.csv"
    kind = args.data_kind or "synthetic"
    if args.input and args.data_kind is None:
        raise ValueError("An imported CSV needs --data-kind synthetic or --data-kind real")
    if kind == "real" and SAMPLES.resolve() in source.parents:
        raise ValueError("Bundled samples cannot be labeled as real measurements")
    revision = args.revision or ("synthetic-fixture-v1" if kind == "synthetic" else "")
    if not revision.strip():
        raise ValueError("Real evaluation needs --revision with the measured build identifier")
    trials = read_trials(source)
    # Validate all rows and duplicates before writing any output.
    summary = summarize(trials, expected_trials=args.expected_trials)
    if not args.input:
        expected = json.loads((SAMPLES / "expected_summary.json").read_text(encoding="utf-8"))
        if args.expected_trials == 10 and summary != expected:
            raise ValueError("Synthetic fixture does not match expected_summary.json")
    output = Path(args.output) if args.output else (
        Path(tempfile.gettempdir()) / f"ifelse-tv4-synthetic-{monotonic_ns()}"
        if kind == "synthetic" else ROOT / "results" / f"run-{monotonic_ns()}"
    )
    logger = MetricsLogger(output, data_kind=kind, revision=revision)
    for row in trials:
        logger.save_trial(row)
    events = Path(args.events) if args.events else (SAMPLES / "events.csv" if not args.input else None)
    if events is not None:
        with events.open(newline="", encoding="utf-8-sig") as stream:
            for event in csv.DictReader(stream):
                logger.record_event(event)
    report = write_report(output, expected_trials=args.expected_trials)
    print((output / "summary.md").read_text(encoding="utf-8"))
    print(f"Artifacts: {output.resolve()}")
    return report


def check_environment(args):
    """Check dependencies without importing unfinished team modules."""
    problems = []
    print(f"Python: {platform.python_version()} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    print(f"Virtual environment: {'yes' if sys.prefix != sys.base_prefix else 'no'}")
    expected = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if "==" in line and not line.lstrip().startswith("#"):
            package, version = line.strip().split("==", 1)
            expected[package] = version
    for package, version in expected.items():
        try:
            installed = importlib.metadata.version(package)
            print(f"{package}: {installed} (expected {version})")
            if installed != version:
                problems.append(f"{package}: expected {version}, got {installed}")
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"{package}: not installed")
    for package in ("opencv-python", "opencv-python-headless", "opencv-contrib-python-headless"):
        try:
            version = importlib.metadata.version(package)
            problems.append(f"Conflicting OpenCV distribution: {package}=={version}")
        except importlib.metadata.PackageNotFoundError:
            pass
    for module in ("numpy", "cv2", "mediapipe", "pybullet"):
        try:
            imported = importlib.import_module(module)
            if module == "mediapipe":
                _ = imported.tasks.vision.HandLandmarker
            print(f"Import {module}: OK")
        except Exception as exc:
            problems.append(f"Import {module}: {type(exc).__name__}: {exc}")
    if args.model:
        try:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(Path(args.model).resolve())),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=1,
            )
            with vision.HandLandmarker.create_from_options(options):
                print(f"Hand Landmarker model: OK ({args.model})")
        except Exception as exc:
            problems.append(f"Model load: {type(exc).__name__}: {exc}")
    else:
        print("Model: NOT CHECKED (TV2 supplies it; use --model PATH)")
    if args.check_camera:
        capture = None
        try:
            import cv2
            capture = cv2.VideoCapture(args.camera_index)
            valid, frame = capture.read()
            if not valid or frame is None:
                raise RuntimeError("No frame received; check camera permission/index/other processes")
            print(f"Camera {args.camera_index}: OK ({frame.shape[1]}x{frame.shape[0]})")
        except Exception as exc:
            problems.append(f"Camera: {type(exc).__name__}: {exc}")
        finally:
            if capture is not None:
                capture.release()
    else:
        print("Camera: NOT CHECKED (use --check-camera on the demo machine)")
    if args.check_simulation:
        connection = None
        try:
            import pybullet as p
            connection = p.connect(p.DIRECT)
            if connection < 0:
                raise RuntimeError("DIRECT connection failed")
            p.setGravity(0, 0, -9.81, physicsClientId=connection)
            shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.05] * 3, physicsClientId=connection)
            body = p.createMultiBody(baseMass=1, baseCollisionShapeIndex=shape,
                                     basePosition=[0, 0, 1], physicsClientId=connection)
            for _ in range(24):
                p.stepSimulation(physicsClientId=connection)
            position, _ = p.getBasePositionAndOrientation(body, physicsClientId=connection)
            if position[2] >= 1:
                raise RuntimeError("Physics did not advance")
            print("PyBullet DIRECT physics: OK (GUI/robot scene still require TV3)")
        except Exception as exc:
            problems.append(f"PyBullet DIRECT: {type(exc).__name__}: {exc}")
        finally:
            if connection is not None and connection >= 0:
                p.disconnect(physicsClientId=connection)
    for module in ("contracts.py", "config.py", "main.py", "control.py", "vision.py", "simulation.py"):
        print(f"Handoff {module}: {'present (not executed)' if (ROOT / module).exists() else 'PENDING owner handoff'}")
    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    print("Environment checks passed." if not problems else "Environment checks incomplete/failed.")
    return 1 if problems else 0


def self_check():
    """Boundary, failure and persistence checks; independent of camera/physics."""
    from dev.fakes import FakeSimulator, FakeVision, RobotCommand, TrialRecord, hand_sample, sim_status

    class EvaluationChecks(unittest.TestCase):
        def trial(self, **changes):
            row = dict(trial_id="T1", operator="operator_A", requested_box_id=0,
                       picked_box_id=0, placed_in_bin=True, duration_s=30, failure_reason="")
            row.update(changes)
            return row

        def test_sample_expectations(self):
            expected = json.loads((SAMPLES / "expected_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summarize(read_trials(SAMPLES / "trials.csv")), expected)

        def test_deadline_and_wrong_box(self):
            self.assertEqual(summarize([self.trial()])["successful_trials"], 1)
            self.assertEqual(summarize([self.trial(duration_s=30.001)])["successful_trials"], 0)
            report = summarize([self.trial(picked_box_id=1)])
            self.assertEqual(report["wrong_box_trials"], 1)
            self.assertEqual(report["successful_trials"], 0)

        def test_no_success_for_reset_unplaced_or_missing_box(self):
            for change in (dict(failure_reason="reset"), dict(placed_in_bin=False),
                           dict(picked_box_id=None, placed_in_bin=False)):
                with self.subTest(change=change):
                    self.assertEqual(summarize([self.trial(**change)])["successful_trials"], 0)

        def test_invalid_values_and_duplicate(self):
            for change in (dict(duration_s=-1), dict(duration_s=float("nan")),
                           dict(duration_s=float("inf")), dict(duration_s=True),
                           dict(placed_in_bin="maybe"), dict(picked_box_id=None),
                           dict(trial_id=""), dict(operator="")):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    summarize([self.trial(**change)])
            with self.assertRaises(ValueError):
                summarize([self.trial(), self.trial()])

        def test_empty_and_insufficient_operators(self):
            empty = summarize([])
            self.assertIsNone(empty["median_success_duration_s"])
            self.assertIsNone(empty["success_rate_completed"])
            self.assertFalse(empty["evaluation_complete"])
            rows = [self.trial(trial_id=str(i)) for i in range(10)]
            self.assertFalse(summarize(rows)["internal_goal_met"])

        def test_logger_roundtrip_and_reset_preserves_trials(self):
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "synthetic"
                logger = MetricsLogger(path, data_kind="synthetic", revision="self-check")
                record = TrialRecord(**self.trial())
                logger.save_trial(record)
                with self.assertRaises(ValueError):
                    logger.save_trial(record)
                logger.record_event(dict(timestamp=100, event_type="RESET", reason="operator_reset"))
                logger.save_trial(self.trial(trial_id="T2", placed_in_bin=False, failure_reason="reset"))
                with self.assertRaises(ValueError):
                    logger.record_event(dict(timestamp=99, event_type="BAD_CLOCK"))
                report = write_report(path)
                self.assertEqual(report["completed_trials"], 2)
                self.assertEqual(report["successful_trials"], 1)
                self.assertIn("DỮ LIỆU MẪU", (path / "summary.md").read_text(encoding="utf-8"))
                with self.assertRaises(FileExistsError):
                    MetricsLogger(path, data_kind="synthetic", revision="self-check")

        def test_provenance_guard(self):
            with tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(ValueError):
                    MetricsLogger(Path(temp) / "results" / "sample", data_kind="synthetic", revision="sample")
                with self.assertRaises(ValueError):
                    MetricsLogger(Path(temp) / "real", data_kind="real", revision="")
                logger = MetricsLogger(Path(temp) / "real", data_kind="real", revision="test-only")
                logger.save_trial(self.trial())
                self.assertEqual(write_report(logger.output_dir)["data_kind"], "real")

        def test_fake_feedback_is_explicit(self):
            fake = FakeSimulator([
                sim_status(candidate_box_id=0),
                sim_status(held_box_id=0),
                sim_status(placed_box_ids=(0,)),
            ], attach_results={0: True})
            fake.initialize()
            command = RobotCommand(target_xyz=(0.5, 0, 0.4), gripper_closed=True)
            self.assertFalse(fake.try_attach(1))
            self.assertTrue(fake.try_attach(0))
            self.assertIsNone(fake.step(command, 1 / 60).held_box_id)
            self.assertEqual(fake.step(command, 1 / 60).held_box_id, 0)
            fake.release()
            self.assertEqual(tuple(fake.step(command, 1 / 60).placed_box_ids), (0,))
            fake.reset()
            self.assertEqual(fake.actions, [])
            self.assertEqual(fake.commands, [])
            self.assertIsNone(fake.step(command, 1 / 60).held_box_id)
            fake.close()
            with self.assertRaises(RuntimeError):
                fake.step(command, 1 / 60)

        def test_fake_vision_tracks_loss_without_consuming_reads(self):
            valid = hand_sample(now=100)
            lost = hand_sample(frame_id=1, now=101, valid=False)
            vision = FakeVision([valid, lost])
            vision.start()
            self.assertIs(vision.latest_sample(), valid)
            self.assertIs(vision.latest_sample(), valid)
            self.assertFalse(vision.advance().valid)
            self.assertFalse(vision.latest_sample().valid)
            vision.close()
            with self.assertRaises(RuntimeError):
                vision.latest_sample()

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EvaluationChecks))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", help="Run stdlib evaluation/fake checks")
    parser.add_argument("--check-env", action="store_true", help="Check installed dependencies and handoff files")
    parser.add_argument("--check-camera", action="store_true", help="With --check-env: open and release camera once")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--check-simulation", action="store_true", help="With --check-env: verify DIRECT physics")
    parser.add_argument("--model", help="With --check-env: verify TV2's Hand Landmarker .task file")
    parser.add_argument("--input", help="Trial CSV; omit for bundled synthetic fixtures")
    parser.add_argument("--events", help="Optional event CSV, with monotonic timestamps")
    parser.add_argument("--data-kind", choices=("synthetic", "real"))
    parser.add_argument("--revision", help="Measured commit/build identifier (required for real CSV)")
    parser.add_argument("--output", help="A fresh output directory; synthetic output cannot be in results/")
    parser.add_argument("--expected-trials", type=int, default=10)
    args = parser.parse_args()
    if args.self_check and args.check_env:
        parser.error("Use --self-check and --check-env separately")
    if (args.check_camera or args.check_simulation or args.model) and not args.check_env:
        parser.error("Camera, model and simulation probes require --check-env")
    try:
        if args.self_check:
            return self_check()
        if args.check_env:
            return check_environment(args)
        run_report(args)
        return 0
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
