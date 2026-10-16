"""Camera/physics independent controller. Only confirmed feedback advances a pick.

Call update once per control tick with the newest sample and real SimStatus.
Actions are one-shot; the orchestrator executes them exactly once. No command
queue is needed. Resume is explicit and additionally requires a stable open hand.
"""

from math import dist, exp, isfinite
from typing import NamedTuple

from config import Config, DEFAULT_CONFIG
from contracts import Action, ControllerState as State, Event, HandSample, RobotCommand, SimStatus


def clamp(value, bounds):
    return max(bounds[0], min(bounds[1], value))


class HandFeatures(NamedTuple):
    u: float
    v: float
    pinch_ratio: float


def extract_hand_features(sample, config=DEFAULT_CONFIG):
    """Validate the full arm/hand contract and derive pixel-correct gestures."""
    if (not isinstance(sample, HandSample) or not sample.valid
            or not sample.pose_valid or not sample.hand_valid
            or sample.arm_side != config.hand_side):
        return None
    try:
        w, h = sample.image_width, sample.image_height
        if not all(isfinite(v) and v > 0 for v in (w, h)):
            return None
        arm = [sample.arm_keypoints[name] for name in ("shoulder", "elbow", "wrist")]
        if any(len(p) != 5 or not all(isfinite(v) for v in p)
               or not all(0 <= v <= 1 for v in p[:2])
               or not all(config.pick_pose_retain <= v <= 1 for v in p[3:]) for p in arm):
            return None
        points = sample.hand_keypoints
        if len(points) != 21 or any(len(p) != 3 or not all(isfinite(v) for v in p)
                                   or not all(0 <= v <= 1 for v in p[:2]) for p in points):
            return None
        pixels = [(p[0] * w, p[1] * h) for p in points]
        if dist(pixels[0], (arm[2][0] * w, arm[2][1] * h)) > config.wrist_match_max_ratio * min(w, h):
            return None
        scale = dist(pixels[0], pixels[9])
        if scale <= 0 or scale < config.hand_min_palm_px:
            return None
        palm = [points[i] for i in (0, 5, 9, 13, 17)]
        return HandFeatures(*(sum(p[i] for p in palm) / 5 for i in (0, 1)),
                            dist(pixels[4], pixels[8]) / scale)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


class Controller:
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        self.reset()

    def reset(self):
        self.state = State.READY
        self.message = "Show an open hand to arm"
        self.target = self.config.home_xyz
        self._last_now = None
        self._last_frame = -1
        self._last_capture = float("-inf")
        self._gesture = None
        self._pending_gesture = None
        self._gesture_since = None
        self._tracking_since = None
        self._armed = False
        self._resume_requested = False
        self._resume_ready = False
        self.pause_reason = ""
        self._entered_at = 0.0
        self._action_sent_at = None
        self._selected = None
        self._events = []
        self._placed = set()
        self._filtered_xy = self.target[:2]

    def drain_events(self) -> list[Event]:
        events, self._events = self._events, []
        return events

    def _event(self, now, name, reason="", box_id=None):
        self._events.append(Event(now, name, box_id=box_id or self._selected,
                                  controller_state=self.state.value, reason=reason))

    def _transition(self, state, now):
        self.state = state
        self.message = {
            State.READY: "Show an open hand to arm",
            State.LOWERING_PICK: "Lowering to selected box",
            State.LIFTING: "Lifting to transport height",
            State.CARRYING: "Move to bin and open hand",
            State.LOWERING_PLACE: "Lowering into bin",
            State.RELEASING: "Waiting for placement confirmation",
            State.PAUSED: "Paused: show open hand, then press resume",
        }[state]
        self._entered_at = now
        self._action_sent_at = None
        self._event(now, "state_changed")

    def pause(self, status: SimStatus, now: float, reason="manual_pause"):
        if self.state != State.PAUSED:
            self._transition(State.PAUSED, now)
            # Hold the actual current EE, never keep driving toward the old target.
            self.target = status.ee_xyz
            self._filtered_xy = status.ee_xyz[:2]
            self._tracking_since = None
            self._gesture = self._pending_gesture = None
            self._gesture_since = None
            self._armed = False
            self._resume_requested = False
            self._event(now, "paused", reason)
        self.pause_reason = reason
        self._resume_ready = False
        self.message = f"Paused ({reason}): open hand and wait for stable tracking"

    def request_resume(self):
        # Never queue a C press through a future tracking loss/recovery.
        # The operator must confirm AFTER seeing stable tracking, not before.
        if self.state == State.PAUSED and self._resume_ready:
            self._resume_requested = True
            return True
        return False

    def _tracking_problem(self, sample, now):
        if not isinstance(sample, HandSample):
            return "waiting_for_camera"
        if not all(isfinite(x) for x in (sample.captured_at, sample.processed_at)):
            return "invalid_timestamp"
        if now - sample.captured_at > self.config.sample_max_age_s:
            return "sample_stale"
        if not sample.captured_at <= sample.processed_at <= now:
            return "invalid_timestamp"
        if sample.frame_id < self._last_frame or sample.captured_at < self._last_capture:
            return "out_of_order_frame"
        if not sample.pose_valid:
            return "pose_lost"
        if not sample.hand_valid:
            return "hand_lost"
        if not sample.valid:
            return "wrist_not_matched"
        if extract_hand_features(sample, self.config) is None:
            return "invalid_landmarks_or_small_palm"
        return None

    def _valid(self, sample, now):
        return self._tracking_problem(sample, now) is None

    def _observe(self, sample, ratio):
        """Only new frames contribute evidence; a cached frame cannot arm a gesture."""
        if sample.frame_id <= self._last_frame:
            return None
        self._last_frame = sample.frame_id
        self._last_capture = sample.captured_at
        candidate = ("closed" if ratio <= self.config.pinch_close else
                     "open" if ratio >= self.config.pinch_open else None)
        if candidate is None:
            self._pending_gesture = None
            self._gesture_since = None
            return None
        if candidate != self._pending_gesture:
            self._pending_gesture = candidate
            self._gesture_since = sample.captured_at
        if sample.captured_at - self._gesture_since < self.config.gesture_hold_s:
            return None
        changed = candidate != self._gesture
        self._gesture = candidate
        return candidate if changed else None

    def _in_bin(self, xy):
        c = self.config
        return all(abs(p - center) <= half - c.bin_margin
                   for p, center, half in zip(xy, c.bin_center, c.bin_half_size))

    def _near_target(self, status):
        return status.target_reached and dist(status.ee_xyz, self.target) <= self.config.position_tolerance

    def _move(self, desired, dt):
        c = self.config
        desired = (clamp(desired[0], c.workspace_x), clamp(desired[1], c.workspace_y),
                   clamp(desired[2], (min(c.pick_z, c.place_z), c.transport_z)))
        distance = dist(self.target, desired)
        fraction = min(1.0, c.max_speed * dt / distance) if distance else 1.0
        self.target = tuple(a + fraction * (b - a) for a, b in zip(self.target, desired))

    def _hold(self, status):
        return RobotCommand(self.target, status.held_box_id is not None, hold_position=True)

    def update(self, sample: HandSample | None, sim_status: SimStatus, now: float) -> RobotCommand:
        if not isfinite(now) or (self._last_now is not None and now < self._last_now):
            raise ValueError("now must be finite and monotonic")
        c, status = self.config, sim_status
        dt = min(c.max_control_dt, max(0, now - self._last_now)) if self._last_now is not None else 0.0
        if self._last_now is None:
            self.target = status.ee_xyz
            self._filtered_xy = status.ee_xyz[:2]
        stalled = self._last_now is not None and now - self._last_now > c.sample_max_age_s
        self._last_now = now
        problem = self._tracking_problem(sample, now)
        if problem is not None:
            self.pause(status, now, problem)
            self._tracking_since = None
            self._pending_gesture = self._gesture = None
            self._gesture_since = None
            self._resume_requested = False
            return self._hold(status)

        # A fresh frame after a stalled consumer/producer is not evidence that
        # tracking or a gesture stayed stable throughout the missing interval.
        if stalled or (isfinite(self._last_capture)
                       and sample.captured_at - self._last_capture > c.sample_max_age_s):
            self.pause(status, now, "tracking_gap")
            self._tracking_since = None
            self._pending_gesture = self._gesture = None
            self._gesture_since = None
            self._armed = self._resume_requested = False

        features = extract_hand_features(sample, c)
        edge = self._observe(sample, features.pinch_ratio)
        if self._tracking_since is None:
            self._tracking_since = sample.captured_at
        stable = sample.captured_at - self._tracking_since >= c.tracking_stable_s
        if self.state == State.PAUSED:
            open_duration = (sample.captured_at - self._gesture_since
                             if self._pending_gesture == "open" and self._gesture_since is not None else 0)
            self._resume_ready = (stable and self._gesture == "open"
                                  and open_duration >= c.resume_stable_s
                                  and sample.captured_at - self._tracking_since >= c.resume_stable_s)
            if not (self._resume_requested and self._resume_ready):
                self._resume_requested = False
                self.message = ("Tracking stable: tap C once to resume" if self._resume_ready else
                                f"Paused ({self.pause_reason}): keep open hand stable {c.resume_stable_s:.2f}s")
                return self._hold(status)
            # Cancel interrupted trajectories. Lift from the current XY; inspect
            # held feedback instead of replaying an uncertain attach/release.
            self._selected = status.held_box_id
            self._transition(State.LIFTING, now)
            self._event(now, "resumed", "lift_from_current_pose")
            self._resume_requested = False
            self._resume_ready = False
            self._armed = False
            edge = None

        if stable and self._gesture == "open" and self._pending_gesture == "open":
            self._armed = True
        action = Action.NONE
        desired = self.target
        moving_hand = self.state in (State.READY, State.CARRYING)
        if moving_hand:
            left, top, right, bottom = c.image_rect
            u = clamp((features.u - left) / (right - left), (0, 1))
            v = clamp((features.v - top) / (bottom - top), (0, 1))
            xy = (c.workspace_x[0] + u * (c.workspace_x[1] - c.workspace_x[0]),
                  c.workspace_y[1] - v * (c.workspace_y[1] - c.workspace_y[0]))
            alpha = 1 - exp(-dt / c.smoothing_tau) if c.smoothing_tau > 0 else 1
            self._filtered_xy = tuple(a + alpha * (b - a) for a, b in zip(self._filtered_xy, xy))
            desired = (*self._filtered_xy, c.transport_z)

        if self.state == State.READY:
            self.message = "Pinch above a highlighted box" if self._armed else "Show an open hand to arm"
            if edge == "closed" and self._armed:
                self._armed = False
                positions = {box_id: xyz for box_id, xyz, _ in c.boxes}
                box = status.candidate_box_id
                if box in positions and box not in status.placed_box_ids and status.held_box_id is None:
                    self._selected = box
                    self._transition(State.LOWERING_PICK, now)
                    desired = (*positions[box][:2], c.pick_z)
                else:
                    self.message = "No eligible box under gripper; open hand to retry"
                    self._event(now, "pick_rejected", "no_candidate")
        elif self.state == State.LOWERING_PICK:
            xyz = next(xyz for box_id, xyz, _ in c.boxes if box_id == self._selected)
            desired = (*xyz[:2], c.pick_z)
            if status.held_box_id == self._selected:
                self._event(now, "picked")
                self._transition(State.LIFTING, now)
            elif self._action_sent_at is not None:
                if now - self._action_sent_at >= c.action_timeout_s:
                    self._event(now, "pick_failed", "attach_not_confirmed")
                    self._transition(State.LIFTING, now)
            elif (dist(self.target, desired) <= c.position_tolerance and self._near_target(status)):
                action = Action.ATTACH
                self._action_sent_at = now
                self._event(now, "attach_requested")
        elif self.state == State.LIFTING:
            desired = (*self.target[:2], c.transport_z)
            if dist(self.target, desired) <= c.position_tolerance and self._near_target(status):
                self._filtered_xy = self.target[:2]
                self._transition(State.CARRYING if status.held_box_id else State.READY, now)
                if status.held_box_id is None:
                    self._selected = None
        elif self.state == State.CARRYING:
            self.message = "Move to bin and open hand"
            if status.held_box_id != self._selected:
                self._event(now, "carry_failed", "held_box_lost")
                self.pause(status, now, "held_box_lost")
                return self._hold(status)
            if edge == "open":
                if self._in_bin(status.ee_xyz[:2]) and self._in_bin(desired[:2]):
                    self._transition(State.LOWERING_PLACE, now)
                    desired = (*status.ee_xyz[:2], c.place_z)
                else:
                    self.message = "Move into bin; pinch and open again to place"
                    self._event(now, "place_rejected", "outside_bin")
        elif self.state == State.LOWERING_PLACE:
            desired = (*self.target[:2], c.place_z)
            if dist(self.target, desired) <= c.position_tolerance and self._near_target(status):
                action = Action.RELEASE
                self._transition(State.RELEASING, now)
                self._action_sent_at = now
                self._event(now, "release_requested")
        elif self.state == State.RELEASING:
            if status.held_box_id is None and now - self._entered_at >= c.placement_settle_s:
                if self._selected in status.placed_box_ids:
                    if self._selected not in self._placed:
                        self._placed.add(self._selected)
                        self._event(now, "placed")
                    self._transition(State.LIFTING, now)
                elif now - self._entered_at >= c.action_timeout_s:
                    self._event(now, "place_failed", "box_not_in_bin")
                    self._transition(State.LIFTING, now)
            elif now - self._entered_at >= c.action_timeout_s:
                self.pause(status, now, "release_not_confirmed")
        if self.state not in (State.READY, State.CARRYING, State.PAUSED) and now - self._entered_at > c.motion_timeout_s:
            self.pause(status, now, "motion_timeout")
        if self.state != State.PAUSED:
            self._move(desired, dt)
        if self.state == State.PAUSED:
            return self._hold(status)
        closed = ((status.held_box_id is not None or action == Action.ATTACH)
                  and action != Action.RELEASE and self.state != State.RELEASING)
        return RobotCommand(self.target, closed, action, self._selected if action != Action.NONE else None)
