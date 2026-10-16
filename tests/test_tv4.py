"""Integration boundaries between the TV4 tools and the current application."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from control import extract_hand_features
from contracts import HandSample, RobotCommand, SimStatus
from dev.fakes import FakeSimulator, FakeVision, hand_sample, sim_status
from metrics import Metrics, read_trials, summarize


class TV4IntegrationTests(unittest.TestCase):
    def test_fake_uses_raw_contract_and_zero_dt_does_not_consume_feedback(self):
        vision = FakeVision([hand_sample(now=1)])
        vision.start()
        sample = vision.latest_sample()
        self.assertIsInstance(sample, HandSample)
        self.assertIsNotNone(extract_hand_features(sample))
        statuses = [sim_status(candidate_box_id="green"), sim_status(held_box_id="green")]
        sim = FakeSimulator(statuses)
        self.assertIsInstance(sim.initialize(), SimStatus)
        command = RobotCommand((.5, 0, .35), False)
        self.assertIs(sim.step(command, 0), statuses[0])
        self.assertIs(sim.step(command, 1/60), statuses[0])
        self.assertIs(sim.step(command, 1/60), statuses[1])
        self.assertIs(sim.reset(), statuses[0])

    def test_runtime_csv_can_be_evaluated_by_tv4_without_schema_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            metrics = Metrics(directory=directory)
            try:
                metrics.begin_trial(0)
                metrics.record_event(dict(timestamp=1, event_type="picked", box_id="green"))
                metrics.record_event(dict(timestamp=2, event_type="placed", box_id="green"))
                metrics.begin_trial(3)
                metrics.record_event(dict(timestamp=4, event_type="reset"))
                report = summarize(read_trials(metrics.directory / "trials.csv"))
                self.assertEqual(report["completed_trials"], 2)
                self.assertEqual(report["successful_trials"], 1)
                self.assertEqual(report["failure_counts"], {"reset": 1})
            finally:
                metrics.close()

    def test_cli_synthetic_report_supports_legacy_windows_output_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report"
            env = dict(os.environ, PYTHONIOENCODING="cp1252")
            result = subprocess.run([sys.executable, "-m", "dev.run_metrics", "--output", str(output)],
                                    capture_output=True, env=env, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
            self.assertIn("DỮ LIỆU MẪU", result.stdout.decode("utf-8"))
            self.assertTrue((output / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
