"""Kiểm thử logic cốt lõi không cần webcam: python -m pytest tests  (hoặc python tests/test_core.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from perception.filters import OneEuroFilter  # noqa: E402
from perception.fusion import HAND_OFFSET, POSE_IDX, ArmHandFusion, canonical_points  # noqa: E402
from perception.landmarker import HandDetection, RawDetection  # noqa: E402
from sim.transforms import R_MP_TO_SIM, mp_to_sim, quat_z_to, sim_to_mp  # noqa: E402

HIP_TO_SHOULDER = {"left": np.array([0.18, -0.5, 0.0]), "right": np.array([-0.18, -0.5, 0.0])}


def fake_detection(t: float, sides=("right",), with_hands=True, hand_label_wrong=False, with_pose=True) -> RawDetection:
    """Dựng RawDetection giả: pose gốc ở hông, hand gốc ở tâm bàn tay (như MediaPipe)."""
    det = RawDetection(timestamp=t)
    if with_pose:
        det.pose_world = np.zeros((33, 3))
        det.pose_image = np.full((33, 3), 0.5)
        det.pose_visibility = np.ones(33)
        for s in ("left", "right"):
            pts = canonical_points(s) + HIP_TO_SHOULDER[s]
            for k, idx in enumerate(POSE_IDX[s]):
                det.pose_world[idx] = pts[k]
                det.pose_image[idx] = [0.5 + pts[k][0], 0.5 + pts[k][1], 0]  # "chiếu" đơn giản
    if with_hands:
        for s in sides:
            hand = canonical_points(s)[HAND_OFFSET:]
            world = hand - hand.mean(axis=0)  # gốc quanh tâm bàn tay
            wrist_img = det.pose_image[POSE_IDX[s][2]] if with_pose else np.array([0.5, 0.5, 0])
            image = np.tile(wrist_img, (21, 1)) + np.c_[world[:, :2], np.zeros(21)]
            label = s if not hand_label_wrong else ("left" if s == "right" else "right")
            det.hands.append(HandDetection(side=label, score=0.9, world=world, image=image))
    return det


def test_transform_and_quaternion() -> None:
    assert np.isclose(np.linalg.det(R_MP_TO_SIM), 1.0)
    assert np.allclose(mp_to_sim([0, 1, 0]), [0, 0, -1])   # xuống (mp) -> -Z (sim)
    assert np.allclose(mp_to_sim([0, 0, -1]), [1, 0, 0])   # về phía camera -> +X (trước mặt)
    pts = np.random.default_rng(0).normal(size=(24, 3))
    assert np.allclose(sim_to_mp(mp_to_sim(pts, [0, 0, 1.4], 2.0), [0, 0, 1.4], 2.0), pts)
    for d in [[1, 0, 0], [0, 0, -1], [0.3, -0.2, 0.9]]:
        x, y, z, w = quat_z_to(np.array(d, float))
        rz = np.array([2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)])  # cột Z của ma trận quay
        assert np.allclose(rz, np.array(d) / np.linalg.norm(d), atol=1e-6)


def test_one_euro_reduces_jitter() -> None:
    rng = np.random.default_rng(1)
    f = OneEuroFilter(1.0, 4.0, 1.0)
    out = np.array([f(np.array([rng.normal(0, 0.01)]), i / 30)[0] for i in range(90)])
    assert out[30:].std() < 0.5 * 0.01


def test_fusion_joins_hand_to_wrist_and_shoulder_origin() -> None:
    fu = ArmHandFusion({"hands": "right"}, {})
    f = fu.update(fake_detection(0.0))["right"]
    assert f.valid
    assert np.allclose(f.shoulder, 0)                       # gốc = vai
    assert np.allclose(f.hand[0], f.wrist)                  # điểm 0 bàn tay trùng cổ tay pose
    assert np.allclose(f.points(), canonical_points("right"), atol=1e-9)


def test_fusion_matches_by_position_even_if_label_wrong() -> None:
    fu = ArmHandFusion({"hands": "both"}, {})
    frames = fu.update(fake_detection(0.0, sides=("left", "right"), hand_label_wrong=True))
    assert all(f.valid for f in frames.values())
    assert np.allclose(frames["left"].hand[0], frames["left"].wrist)
    # Gốc ở trung điểm hai vai -> hai vai đối xứng
    assert np.allclose(frames["left"].shoulder, -frames["right"].shoulder)


def test_hold_then_invalid() -> None:
    fu = ArmHandFusion({"hands": "right", "hold_time": 0.5}, {})
    fu.update(fake_detection(0.0))
    assert fu.update(fake_detection(0.3, with_hands=False))["right"].valid      # mất tay < 0.5 s
    assert not fu.update(fake_detection(0.7, with_hands=False))["right"].valid  # > 0.5 s
    assert fu.update(fake_detection(0.8))["right"].valid                        # tìm lại
    assert fu.update(fake_detection(1.1, with_pose=False))["right"].valid       # mất pose < 0.5 s
    f = fu.update(fake_detection(1.4, with_pose=False))["right"]
    assert not f.valid and np.allclose(f.points(), canonical_points("right"))   # giữ tư thế cuối


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
