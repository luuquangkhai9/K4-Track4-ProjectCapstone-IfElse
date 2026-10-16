"""TV4: append-only trial/event logging and reproducible evaluation (stdlib only).

Accepts mappings or contract objects. Does not import camera, robot or controller.
Timestamps in events are monotonic seconds, not wall-clock timestamps.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

TRIAL_FIELDS = (
    "trial_id", "operator", "requested_box_id", "picked_box_id",
    "placed_in_bin", "duration_s", "failure_reason",
)
EVENT_FIELDS = (
    "timestamp", "event_type", "trial_id", "box_id", "controller_state", "reason",
)
TIME_LIMIT_S = 30.0


def _value(record, key, default=None):
    return record.get(key, default) if isinstance(record, Mapping) else getattr(record, key, default)


def _text(value):
    return "" if value is None else str(value).strip()


def _number(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite, nonnegative number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite, nonnegative number") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a finite, nonnegative number")
    return number


def _boolean(value):
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in ("true", "1"):
        return True
    if str(value).strip().lower() in ("false", "0"):
        return False
    raise ValueError("placed_in_bin must be true/false or 1/0")


def normalize_trial(trial):
    row = {key: _value(trial, key) for key in TRIAL_FIELDS}
    for key in ("trial_id", "operator", "requested_box_id"):
        row[key] = _text(row[key])
        if not row[key]:
            raise ValueError(f"Missing {key}")
    row["picked_box_id"] = _text(row["picked_box_id"])
    row["failure_reason"] = _text(row["failure_reason"])
    row["placed_in_bin"] = _boolean(row["placed_in_bin"])
    row["duration_s"] = _number(row["duration_s"], "duration_s")
    if row["placed_in_bin"] and not row["picked_box_id"]:
        raise ValueError("A placed box must have picked_box_id")
    return row


def trial_outcome(trial):
    """An explicit failure (reset/abort included) always overrides a placement."""
    row = normalize_trial(trial)
    if row["failure_reason"]:
        return row["failure_reason"]
    if row["picked_box_id"] and row["picked_box_id"] != row["requested_box_id"]:
        return "wrong_box"
    if row["duration_s"] > TIME_LIMIT_S:
        return "timeout"
    if not row["picked_box_id"]:
        return "not_picked"
    if not row["placed_in_bin"]:
        return "not_in_bin"
    return "success"


def read_trials(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(TRIAL_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        rows = []
        seen = set()
        for line, raw in enumerate(reader, 2):
            try:
                row = normalize_trial(raw)
                if row["trial_id"] in seen:
                    raise ValueError(f"Duplicate trial_id: {row['trial_id']}")
            except ValueError as exc:
                raise ValueError(f"{path}:{line}: {exc}") from exc
            seen.add(row["trial_id"])
            rows.append(row)
    return rows


def summarize(trials, *, expected_trials=10):
    if isinstance(expected_trials, bool) or not isinstance(expected_trials, int) or expected_trials < 1:
        raise ValueError("expected_trials must be a positive integer")
    rows = [normalize_trial(trial) for trial in trials]
    if len({row["trial_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate trial_id; reset must not erase or overwrite a trial")
    outcomes = [trial_outcome(row) for row in rows]
    durations = [row["duration_s"] for row, outcome in zip(rows, outcomes) if outcome == "success"]
    operators = sorted({row["operator"] for row in rows})
    return {
        "completed_trials": len(rows),
        "expected_trials": expected_trials,
        "successful_trials": len(durations),
        "success_rate_completed": len(durations) / len(rows) if rows else None,
        "wrong_box_trials": sum(bool(row["picked_box_id"]) and row["picked_box_id"] != row["requested_box_id"] for row in rows),
        "median_success_duration_s": median(durations) if durations else None,
        "median_sample_count": len(durations),
        "operators": operators,
        "evaluation_complete": len(rows) == expected_trials and len(operators) >= 2,
        "internal_goal_met": len(rows) == 10 and len(operators) >= 2 and len(durations) >= 8,
        "failure_counts": dict(sorted(Counter(outcome for outcome in outcomes if outcome != "success").items())),
    }


def validate_output_dir(output_dir, data_kind):
    if data_kind not in ("synthetic", "real"):
        raise ValueError("data_kind must be synthetic or real")
    path = Path(output_dir).resolve()
    if data_kind == "synthetic" and "results" in (part.casefold() for part in path.parts):
        raise ValueError("Synthetic data must stay outside results/ (use /tmp or dev/)")
    return path


class MetricsLogger:
    """One fresh directory per run; never truncate or silently resume evidence.

    main.py owns lifecycle and passes in events and final TrialRecord objects.
    All logger calls must use one owning thread (or caller-side synchronization).
    """

    def __init__(self, output_dir, *, data_kind, revision):
        self.output_dir = validate_output_dir(output_dir, data_kind)
        if not _text(revision):
            raise ValueError("A revision/build identifier is required")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Exclusive metadata creation makes accidental reuse an explicit error.
        with (self.output_dir / "run.json").open("x", encoding="utf-8") as stream:
            json.dump({
                "schema_version": 1, "data_kind": data_kind, "revision": str(revision),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "event_clock": "monotonic_seconds", "time_limit_s": TIME_LIMIT_S,
            }, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        self._trial_ids = set()
        self._last_event_timestamp = None
        for filename, fields in (("trials.csv", TRIAL_FIELDS), ("events.csv", EVENT_FIELDS)):
            with (self.output_dir / filename).open("x", newline="", encoding="utf-8") as stream:
                csv.DictWriter(stream, fieldnames=fields).writeheader()

    def _append(self, filename, fields, row):
        with (self.output_dir / filename).open("a", newline="", encoding="utf-8") as stream:
            csv.DictWriter(stream, fieldnames=fields).writerow(row)
            stream.flush()

    def record_event(self, event):
        row = {key: _value(event, key, "") for key in EVENT_FIELDS}
        row["timestamp"] = _number(row["timestamp"], "timestamp")
        row["event_type"] = _text(row["event_type"])
        if not row["event_type"]:
            raise ValueError("Missing event_type")
        if self._last_event_timestamp is not None and row["timestamp"] < self._last_event_timestamp:
            raise ValueError("Event timestamps must be nondecreasing monotonic seconds")
        for key in EVENT_FIELDS[2:]:
            row[key] = _text(row[key])
        self._append("events.csv", EVENT_FIELDS, row)
        self._last_event_timestamp = row["timestamp"]

    def save_trial(self, trial):
        row = normalize_trial(trial)
        if row["trial_id"] in self._trial_ids:
            raise ValueError(f"Duplicate trial_id: {row['trial_id']}")
        self._append("trials.csv", TRIAL_FIELDS, row)
        self._trial_ids.add(row["trial_id"])


def write_report(output_dir, *, expected_trials=10):
    directory = Path(output_dir)
    metadata = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    validate_output_dir(directory, metadata["data_kind"])
    report = summarize(read_trials(directory / "trials.csv"), expected_trials=expected_trials)
    report.update(data_kind=metadata["data_kind"], revision=metadata["revision"])
    (directory / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    label = "DỮ LIỆU MẪU — KHÔNG PHẢI KẾT QUẢ DEMO" if report["data_kind"] == "synthetic" else "KẾT QUẢ ĐO THẬT — THEO DỮ LIỆU ĐÃ GHI"
    value = report["median_success_duration_s"]
    median_text = "chưa có lượt thành công" if value is None else f"{value:g} giây (n={report['median_sample_count']})"
    lines = [
        f"# {label}", "", f"Phiên bản: `{report['revision']}`.", "",
        f"- Đã ghi: {report['completed_trials']}/{expected_trials} lượt.",
        f"- Thành công: {report['successful_trials']}/{report['completed_trials']} lượt đã ghi.",
        f"- Gắp nhầm: {report['wrong_box_trials']} lượt.",
        f"- Thời gian trung vị các lượt thành công: {median_text}.",
        f"- Số người thao tác: {len(report['operators'])}.",
        f"- Đủ số lượt và ít nhất hai người: {'có' if report['evaluation_complete'] else 'chưa'}.",
        f"- Đạt mục tiêu nội bộ 8/10: {'có' if report['internal_goal_met'] else 'chưa'}.", "",
        "Thành công: đúng hộp, đã vào giỏ, thời gian ≤30 giây, không bị hủy/reset hoặc ghi nhận lỗi.",
        "Không suy ra thành công từ lệnh ATTACH/RELEASE; dùng phản hồi simulator.", "", "## Các lượt thất bại", "",
    ]
    lines.extend(f"- {reason}: {count}" for reason, count in report["failure_counts"].items())
    if not report["failure_counts"]:
        lines.append("Chưa ghi nhận; không thay thế yêu cầu trình bày một ca lỗi đã quan sát.")
    lines.extend(["", "Độ trễ không được suy ra từ duration_s. Đây là thời gian hoàn thành lượt thử.", ""])
    (directory / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return report


# Runtime adapter used by main.py; keep its public API alongside TV4 reports.
from dataclasses import asdict
import importlib.metadata
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
