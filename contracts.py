"""Shared module contracts. This module deliberately uses only the stdlib."""

from dataclasses import dataclass
from enum import Enum

Vec3 = tuple[float, float, float]


class Action(str, Enum):
    NONE = "NONE"
    ATTACH = "ATTACH"
    RELEASE = "RELEASE"


class ControllerState(str, Enum):
    CALIBRATING = "CALIBRATING"
    FOLLOWING = "FOLLOWING"
    READY = "READY"
    LOWERING_PICK = "LOWERING_PICK"
    LIFTING = "LIFTING"
    CARRYING = "CARRYING"
    LOWERING_PLACE = "LOWERING_PLACE"
    RELEASING = "RELEASING"
    PAUSED = "PAUSED"


@dataclass(frozen=True)
class HandSample:
    frame_id: int
    captured_at: float
    processed_at: float
    valid: bool
    u: float = 0.5
    v: float = 0.5
    pinch_ratio: float = 1.0


@dataclass(frozen=True)
class ArmSample:
    frame_id: int
    captured_at: float
    processed_at: float
    valid: bool
    shoulder_xyz: Vec3 = (0.0, 0.0, 0.0)
    elbow_xyz: Vec3 = (0.0, 0.0, 0.0)
    wrist_xyz: Vec3 = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class RobotCommand:
    target_xyz: Vec3
    gripper_closed: bool
    action: Action = Action.NONE
    box_id: str | None = None
    elbow_xyz: Vec3 | None = None
    hold_position: bool = False


@dataclass(frozen=True)
class SimStatus:
    ee_xyz: Vec3
    target_reached: bool
    candidate_box_id: str | None = None
    held_box_id: str | None = None
    placed_box_ids: frozenset[str] = frozenset()
    elbow_xyz: Vec3 | None = None


@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    operator: str
    requested_box_id: str
    picked_box_id: str | None
    placed_in_bin: bool
    duration_s: float
    failure_reason: str = ""


@dataclass(frozen=True)
class Event:
    timestamp: float
    event_type: str
    trial_id: str | None = None
    box_id: str | None = None
    controller_state: str = ""
    reason: str = ""
