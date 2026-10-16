"""Shoulder-relative arm retargeting; no absolute monocular depth or robot I/O."""
from math import dist, exp, isfinite

from config import DEFAULT_CONFIG
from contracts import ArmSample, ControllerState as State, Event, RobotCommand
from control import clamp


def arm_vectors(sample):
    length = dist(sample.shoulder_xyz, sample.elbow_xyz) + dist(sample.elbow_xyz, sample.wrist_xyz)
    def vector(point):
        dx, dy, dz = ((a-b) / length for a, b in zip(point, sample.shoulder_xyz))
        # Camera x right, y down, z away -> robot X forward, Y lateral, Z up.
        return (-dz, dx, -dy)
    return vector(sample.elbow_xyz), vector(sample.wrist_xyz)


def valid_arm(sample, now, config=DEFAULT_CONFIG):
    if not isinstance(sample, ArmSample) or not sample.valid:
        return False
    if not all(isfinite(x) for point in (sample.shoulder_xyz, sample.elbow_xyz, sample.wrist_xyz) for x in point):
        return False
    if not (isfinite(sample.captured_at) and isfinite(sample.processed_at)
            and 0 <= now - sample.captured_at <= config.sample_max_age_s
            and sample.captured_at <= sample.processed_at <= now):
        return False
    upper = dist(sample.shoulder_xyz, sample.elbow_xyz)
    lower = dist(sample.elbow_xyz, sample.wrist_xyz)
    return .06 <= upper <= .65 and .06 <= lower <= .65 and .4 <= upper / lower <= 2.5


class ArmController:
    def __init__(self, config=DEFAULT_CONFIG):
        self.config = config
        self.reset()

    def reset(self):
        self.state = State.PAUSED
        self.message = "Show shoulder/elbow/wrist, hold still, press C to calibrate"
        self._events = []
        self._resume = False
        self._last_now = None
        self._last_frame = -1
        self._last_capture = float("-inf")
        self._calibration = []
        self._reference = None
        self.target = self.config.home_xyz
        self.elbow = None

    def drain_events(self):
        events, self._events = self._events, []
        return events

    def _event(self, now, kind, reason=""):
        self._events.append(Event(now, kind, controller_state=self.state.value, reason=reason))

    def pause(self, status, now, reason="manual_pause"):
        if self.state != State.PAUSED:
            self.state = State.PAUSED
            self._event(now, "paused", reason)
        self.target, self.elbow = status.ee_xyz, status.elbow_xyz
        self._calibration = []
        self._resume = False
        self._reference = None
        self.message = "Paused: show full arm, hold still, press C to recalibrate"

    def request_resume(self):
        if self.state == State.PAUSED:
            self._resume = True

    def _hold(self, status):
        return RobotCommand(status.ee_xyz, status.held_box_id is not None,
                            elbow_xyz=status.elbow_xyz, hold_position=True)

    def _bound_wrist(self, point):
        c = self.config
        point = tuple(clamp(x, bounds) for x, bounds in zip(point,
                      (c.arm_workspace_x, c.arm_workspace_y, c.arm_workspace_z)))
        root = (0, 0, .333)
        radius = dist(root, point)
        if radius > c.arm_reach:
            point = tuple(a + (b-a) * c.arm_reach / radius for a, b in zip(root, point))
        return point

    def update(self, sample, sim_status, now):
        c, status = self.config, sim_status
        if not isfinite(now) or (self._last_now is not None and now < self._last_now):
            raise ValueError("now must be finite and monotonic")
        dt = min(c.max_control_dt, now-self._last_now) if self._last_now is not None else 0
        self._last_now = now
        if not (valid_arm(sample, now, c) and sample.frame_id >= self._last_frame
                and sample.captured_at >= self._last_capture and status.elbow_xyz is not None):
            self.pause(status, now, "arm_missing_low_visibility_or_stale")
            return self._hold(status)
        fresh = sample.frame_id > self._last_frame
        if fresh:
            self._last_frame, self._last_capture = sample.frame_id, sample.captured_at
        if self.state == State.PAUSED:
            if not self._resume or not fresh:
                return self._hold(status)
            self.state = State.CALIBRATING
            self._resume = False
            self._calibration = []
            self.message = "Calibrating: keep the full arm still"
            self._event(now, "arm_calibration_started")
        upper, wrist = arm_vectors(sample)
        if self.state == State.CALIBRATING:
            if fresh:
                # Movement resets the stable window instead of accepting a moving neutral.
                if self._calibration and (dist(wrist, self._calibration[0][2]) > .08
                                          or dist(upper, self._calibration[0][1]) > .08):
                    self._calibration = []
                self._calibration.append((sample.captured_at, upper, wrist))
            if (len(self._calibration) < 5
                    or sample.captured_at-self._calibration[0][0] < c.arm_calibration_s):
                return self._hold(status)
            average = lambda index: tuple(sum(row[index][i] for row in self._calibration) / len(self._calibration) for i in range(3))
            self._reference = (average(1), average(2), status.elbow_xyz, status.ee_xyz)
            self.target, self.elbow = status.ee_xyz, status.elbow_xyz
            self._calibration = []
            self.state = State.FOLLOWING
            self.message = "Following arm XYZ; P pause / C recalibrate after pause"
            self._event(now, "arm_calibrated")
        ref_upper, ref_wrist, robot_elbow, robot_wrist = self._reference
        desired_wrist = self._bound_wrist(tuple(base+c.arm_gain*(value-ref) for base, value, ref in zip(robot_wrist, wrist, ref_wrist)))
        desired_elbow = tuple(base+c.arm_gain*(value-ref) for base, value, ref in zip(robot_elbow, upper, ref_upper))
        # Elbow targets are hints for the robot's redundant IK, not absolute human joints.
        desired_elbow = tuple(clamp(x, bounds) for x, bounds in zip(desired_elbow, ((-.35, .55), (-.45, .45), (.18, .85))))
        alpha = 1-exp(-dt/c.smoothing_tau) if c.smoothing_tau > 0 else 1
        def move(current, desired):
            filtered = tuple(a+alpha*(b-a) for a,b in zip(current, desired))
            distance = dist(current, filtered)
            factor = min(1, c.max_speed*dt/distance) if distance else 1
            return tuple(a+factor*(b-a) for a,b in zip(current, filtered))
        self.target = move(self.target, desired_wrist)
        self.elbow = move(self.elbow, desired_elbow)
        return RobotCommand(self.target, False, elbow_xyz=self.elbow)
