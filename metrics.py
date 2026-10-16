"""Event JSONL and complete trial CSV; synthetic runs use a separate directory."""
import csv
from dataclasses import asdict
from datetime import datetime
import json
import importlib.metadata
from pathlib import Path
import subprocess
import time

from config import DEFAULT_CONFIG
from contracts import TrialRecord


class Metrics:
    def __init__(self, config=DEFAULT_CONFIG, directory="results/live", operator="operator",
                 requested_box_id="green", source="camera"):
        self.directory = Path(directory) / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.directory.mkdir(parents=True, exist_ok=True)
        root = Path(__file__).resolve().parent
        try:
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
        except (OSError, subprocess.CalledProcessError):
            revision, dirty = "unknown", None
        versions = {}
        for package in ("mediapipe", "numpy", "opencv-contrib-python", "pybullet"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = "unavailable"
        (self.directory / "session.json").write_text(json.dumps(
            {"source": source, "revision": revision, "dirty": dirty, "config": asdict(config),
             "dependencies": versions, "operator": operator, "requested_box_id": requested_box_id},
            ensure_ascii=False, indent=2), encoding="utf-8")
        self._events = (self.directory / "events.jsonl").open("w", encoding="utf-8")
        self._trials = (self.directory / "trials.csv").open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._trials, fieldnames=list(TrialRecord.__dataclass_fields__))
        self._writer.writeheader()
        self.operator = operator
        self.requested_box_id = requested_box_id
        self._trial = None
        self._count = 0

    def begin_trial(self, now):
        if self._trial is not None:
            return False
        self._count += 1
        self._trial = {"id": str(self._count), "start": now, "picked": None}
        self.record_event({"timestamp": now, "event_type": "trial_started"})
        return True

    def record_event(self, event):
        event = dict(event)
        if self._trial:
            event["trial_id"] = self._trial["id"]
        self._events.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._events.flush()
        if self._trial:
            now, kind = event["timestamp"], event["event_type"]
            if kind == "picked":
                self._trial["picked"] = event.get("box_id")
            if kind == "placed":
                correct = (self._trial["picked"] == self.requested_box_id
                           and event.get("box_id") == self.requested_box_id)
                self._finish(now, correct and now - self._trial["start"] <= 30,
                             "" if correct else "wrong_box", placed=True)
            elif kind in ("reset", "session_ended", "session_failed"):
                self._finish(now, False, kind)

    def tick(self, now):
        if self._trial and now - self._trial["start"] >= 30:
            self._finish(now, False, "timeout_30s")

    def _finish(self, now, success, reason, placed=False):
        trial, self._trial = self._trial, None
        duration = now - trial["start"]
        if not success and not reason:
            reason = "timeout_30s"
        self.save_trial(TrialRecord(trial["id"], self.operator, self.requested_box_id,
                                    trial["picked"], placed, duration, reason))

    def save_trial(self, trial):
        self._writer.writerow(asdict(trial))
        self._trials.flush()

    def close(self):
        if not self._events.closed:
            if self._trial:
                self._finish(time.monotonic(), False, "session_closed")
            self._events.close()
            self._trials.close()
