"""Shared Z-up meters/seconds; workspace checked with the bundled Panda robot.

Heights refer to panda_grasptarget (link 11). The virtual grasp center is
grasp_offset meters below that link. A different robot needs new IK checks.
"""

from dataclasses import dataclass
from math import pi

from contracts import Vec3


@dataclass(frozen=True)
class Config:
    workspace_x: tuple[float, float] = (0.35, 0.65)
    workspace_y: tuple[float, float] = (-0.25, 0.25)
    # Image mirrored by vision; image up maps to increasing world Y.
    image_rect: tuple[float, float, float, float] = (0.15, 0.15, 0.85, 0.85)
    transport_z: float = 0.35
    pick_z: float = 0.075
    place_z: float = 0.12
    home_xyz: Vec3 = (0.5, 0.0, 0.35)
    downward_euler: Vec3 = (pi, 0.0, 0.0)
    boxes: tuple[tuple[str, Vec3, Vec3], ...] = (
        ("red", (0.40, -0.18, 0.025), (1.0, 0.15, 0.15)),
        ("green", (0.50, -0.18, 0.025), (0.15, 0.8, 0.2)),
        ("blue", (0.60, -0.18, 0.025), (0.15, 0.3, 1.0)),
    )
    bin_center: tuple[float, float] = (0.5, 0.18)
    bin_half_size: tuple[float, float] = (0.12, 0.065)
    bin_margin: float = 0.025
    box_half_size: Vec3 = (0.025, 0.025, 0.025)
    attach_distance: float = 0.035
    position_tolerance: float = 0.015
    max_speed: float = 0.35
    smoothing_tau: float = 0.10
    pinch_close: float = 0.30
    pinch_open: float = 0.50
    gesture_hold_s: float = 0.12
    tracking_stable_s: float = 0.30
    resume_stable_s: float = 0.75
    sample_max_age_s: float = 0.25
    action_timeout_s: float = 1.0
    motion_timeout_s: float = 8.0
    placement_settle_s: float = 0.30
    max_control_dt: float = 0.05
    loop_hz: float = 60.0
    camera_source: int | str = 0
    hand_model: str = "models/hand_landmarker.task"
    pose_model: str = "models/pose_landmarker_lite.task"
    wrist_match_max_ratio: float = 0.12
    # Pick mode: acquire firmly, retain across moderate confidence fluctuations.
    pick_pose_acquire: float = 0.55
    pick_pose_retain: float = 0.40
    hand_side: str = "Right"
    hand_min_palm_px: float = 15.0
    simulation_gui: bool = True
    grasp_offset: float = 0.05
    candidate_distance: float = 0.04
    control_mode: str = "pick"
    arm_visibility: float = 0.65
    arm_calibration_s: float = 0.6
    arm_gain: float = 0.55
    arm_workspace_x: tuple[float, float] = (0.20, 0.65)
    arm_workspace_y: tuple[float, float] = (-0.35, 0.35)
    arm_workspace_z: tuple[float, float] = (0.18, 0.65)
    arm_reach: float = 0.70
    arm_joint_speed: float = 1.2

    def __post_init__(self):
        if not 0 < self.pick_pose_retain <= self.pick_pose_acquire <= 1:
            raise ValueError("pose thresholds must satisfy 0 < retain <= acquire <= 1")
        if not 0 <= self.pinch_close < self.pinch_open:
            raise ValueError("pinch thresholds must have hysteresis")
        if self.max_speed <= 0 or self.loop_hz <= 0 or self.max_control_dt <= 0:
            raise ValueError("speed, frequency and control dt must be positive")
        if any(lo >= hi for lo, hi in (self.workspace_x, self.workspace_y)):
            raise ValueError("workspace bounds must increase")
        left, top, right, bottom = self.image_rect
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError("image_rect must be inside normalized image")


DEFAULT_CONFIG = Config()
