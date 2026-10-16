"""Ghép pose + hand thành một bộ xương 3D liền mạch: vai -> khuỷu -> cổ tay -> 21 điểm bàn tay.

Bố cục mảng điểm (24, 3) dùng chung trong toàn dự án:
    0 = vai, 1 = khuỷu, 2 = cổ tay, 3..23 = điểm bàn tay 0..20 (điểm 3 trùng cổ tay).
Tọa độ ở hệ trục MediaPipe (x: phải ảnh, y: xuống, z: ra xa camera), đơn vị mét,
gốc đặt tại vai (hoặc trung điểm hai vai khi theo dõi cả hai tay).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from perception.filters import OneEuroFilter
from perception.landmarker import HandDetection, RawDetection

NUM_POINTS = 24
SHOULDER, ELBOW, WRIST = 0, 1, 2
HAND_OFFSET = 3  # chỉ số điểm bàn tay i trong mảng 24 điểm là HAND_OFFSET + i

# Chỉ số pose của MediaPipe (theo tay thật của người, với ảnh không lật gương)
POSE_IDX: dict[str, tuple[int, int, int]] = {"left": (11, 13, 15), "right": (12, 14, 16)}

# Kết nối chuẩn của MediaPipe Hands (21 đoạn)
HAND_CONNECTIONS: list[tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 4),            # ngón cái
    (0, 5), (5, 6), (6, 7), (7, 8),            # ngón trỏ
    (5, 9), (9, 10), (10, 11), (11, 12),       # ngón giữa
    (9, 13), (13, 14), (14, 15), (15, 16),     # ngón áp út
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),  # ngón út
]
PALM_CONNECTIONS = {(0, 5), (5, 9), (9, 13), (13, 17), (0, 17)}
# Xương trên mảng 24 điểm: cánh tay trên, cẳng tay, rồi các đốt bàn tay
BONES: list[tuple[int, int]] = [(SHOULDER, ELBOW), (ELBOW, WRIST)] + [
    (HAND_OFFSET + a, HAND_OFFSET + b) for a, b in HAND_CONNECTIONS
]


def finger_of(hand_idx: int) -> str:
    """Tên ngón của điểm bàn tay (0 = cổ tay/lòng bàn tay)."""
    if hand_idx == 0:
        return "palm"
    return ("thumb", "index", "middle", "ring", "pinky")[(hand_idx - 1) // 4]


def parse_sides(hands: str) -> list[str]:
    hands = hands.lower()
    if hands == "both":
        return ["left", "right"]
    if hands not in ("left", "right"):
        raise ValueError(f"perception.hands phải là left | right | both, nhận '{hands}'")
    return [hands]


@dataclass
class ArmHandFrame:
    timestamp: float
    shoulder: np.ndarray   # (3,)
    elbow: np.ndarray      # (3,)
    wrist: np.ndarray      # (3,)
    hand: np.ndarray       # (21, 3)
    confidence: float
    valid: bool
    side: str = "right"

    def points(self) -> np.ndarray:
        """Trả về mảng (24, 3) theo bố cục ở đầu module."""
        return np.vstack([self.shoulder, self.elbow, self.wrist, self.hand])

    @classmethod
    def from_points(cls, pts: np.ndarray, timestamp: float, confidence: float, valid: bool, side: str) -> "ArmHandFrame":
        pts = np.asarray(pts, dtype=np.float64)
        return cls(timestamp, pts[SHOULDER].copy(), pts[ELBOW].copy(), pts[WRIST].copy(),
                   pts[HAND_OFFSET:].copy(), float(confidence), bool(valid), side)


def _unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-9)


def build_arm_points(
    side: str,
    upper_dir: np.ndarray,
    fore_dir: np.ndarray,
    palm_normal: np.ndarray,
    curl: float = 0.2,
    upper_len: float = 0.28,
    fore_len: float = 0.25,
) -> np.ndarray:
    """Dựng bộ xương tay theo tỉ lệ giải phẫu trung bình (dùng cho dữ liệu giả và kích thước mặc định).

    Hoạt động trong mọi hệ trục thuận tay phải. `palm_normal` là hướng lòng bàn tay nhìn ra,
    `curl` (rad) là góc gập ở mỗi khớp ngón.
    """
    u = _unit(np.asarray(fore_dir, float))               # dọc bàn tay (hướng ngón)
    n = _unit(palm_normal - np.dot(palm_normal, u) * u)  # pháp tuyến lòng bàn tay
    v = np.cross(u, n)                                    # phía ngón cái (tay phải)
    if side == "left":
        v = -v  # tay trái là ảnh gương của tay phải

    pts = np.zeros((NUM_POINTS, 3))
    pts[ELBOW] = upper_len * _unit(np.asarray(upper_dir, float))
    pts[WRIST] = pts[ELBOW] + fore_len * u

    def local(a: float, b: float, c: float) -> np.ndarray:
        return pts[WRIST] + a * u + b * v + c * n

    hand = np.zeros((21, 3))
    hand[0] = pts[WRIST]
    # Ngón cái: gập về phía tâm lòng bàn tay theo curl
    k = min(max(curl / 1.2, 0.0), 1.0)
    thumb = np.array([[0.025, 0.022, 0.01], [0.050, 0.045, 0.02], [0.072, 0.058, 0.03], [0.092, 0.066, 0.035]])
    thumb_curled = np.array([[0.025, 0.022, 0.01], [0.050, 0.040, 0.03], [0.068, 0.025, 0.045], [0.080, 0.008, 0.05]])
    for i, (a, b, c) in enumerate((1 - k) * thumb + k * thumb_curled):
        hand[1 + i] = local(a, b, c)
    # Bốn ngón còn lại: (vị trí MCP theo u, v) và độ dài 3 đốt
    fingers = [
        (5, 0.085, 0.025, (0.040, 0.025, 0.020)),
        (9, 0.088, 0.004, (0.045, 0.028, 0.022)),
        (13, 0.082, -0.016, (0.042, 0.026, 0.021)),
        (17, 0.074, -0.034, (0.032, 0.020, 0.018)),
    ]
    for base, a0, b0, lens in fingers:
        p = local(a0, b0, 0.0)
        hand[base] = p
        for j, length in enumerate(lens):
            ang = curl * (j + 1)
            p = p + length * (np.cos(ang) * u + np.sin(ang) * n)
            hand[base + 1 + j] = p
    pts[HAND_OFFSET:] = hand
    return pts


def canonical_points(side: str) -> np.ndarray:
    """Tư thế tham chiếu trong hệ MediaPipe: cánh tay buông xuống, cẳng tay đưa về phía camera."""
    down, toward_cam = np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, -1.0])
    return build_arm_points(side, upper_dir=down, fore_dir=toward_cam, palm_normal=down)


class _SideState:
    def __init__(self, filt: OneEuroFilter) -> None:
        self.filter = filt
        self.last_points: np.ndarray | None = None
        self.last_conf = 0.0
        self.last_good_t = -1e9
        self.last_hand_rel: np.ndarray | None = None  # hình dạng bàn tay (21,3) tương đối cổ tay
        self.last_hand_t = -1e9
        self.valid = False


class ArmHandFusion:
    """Biến RawDetection thành ArmHandFrame (đã đổi gốc về vai, lọc One Euro, xử lý mất dấu)."""

    def __init__(self, perception_cfg: dict, filter_cfg: dict) -> None:
        self.sides = parse_sides(perception_cfg.get("hands", "right"))
        self.hold_time = float(perception_cfg.get("hold_time", 0.5))
        self.min_visibility = float(perception_cfg.get("min_visibility", 0.5))
        self.match_max_dist = float(perception_cfg.get("hand_match_max_dist", 0.15))
        self._states = {
            s: _SideState(OneEuroFilter(filter_cfg.get("min_cutoff", 1.0), filter_cfg.get("beta", 4.0),
                                        filter_cfg.get("d_cutoff", 1.0)))
            for s in self.sides
        }
        self.matched: dict[str, HandDetection] = {}  # tay đã ghép ở frame gần nhất (để vẽ overlay)

    def _origin(self, pose_world: np.ndarray) -> np.ndarray | dict[str, np.ndarray]:
        if len(self.sides) == 2:
            # Theo dõi cả hai tay: gốc là trung điểm hai vai để hai tay không chồng lên nhau
            mid = 0.5 * (pose_world[11] + pose_world[12])
            return {s: mid for s in self.sides}
        return {s: pose_world[POSE_IDX[s][0]] for s in self.sides}

    def _match_hands(self, det: RawDetection) -> dict[str, HandDetection]:
        """Ghép mỗi tay phát hiện được với cổ tay pose gần nhất trên ảnh.

        Khoảng cách 2D giữa điểm 0 của bàn tay và cổ tay của pose là tiêu chí chính
        (bền hơn nhãn handedness vốn đôi khi bị nhầm); sai nhãn chỉ bị phạt nhẹ.
        """
        if det.pose_image is None or not det.hands:
            return {}
        pairs: list[tuple[float, str, int]] = []
        for s in self.sides:
            wrist_img = det.pose_image[POSE_IDX[s][2], :2]
            for i, h in enumerate(det.hands):
                dist = float(np.linalg.norm(h.image[0, :2] - wrist_img))
                if dist <= self.match_max_dist:
                    pairs.append((dist + (0.0 if h.side == s else 0.05), s, i))
        result: dict[str, HandDetection] = {}
        used: set[int] = set()
        for _, s, i in sorted(pairs):  # ghép tham lam theo chi phí tăng dần
            if s not in result and i not in used:
                result[s] = det.hands[i]
                used.add(i)
        return result

    def update(self, det: RawDetection) -> dict[str, ArmHandFrame]:
        t = det.timestamp
        self.matched = self._match_hands(det)
        origins = self._origin(det.pose_world) if det.pose_world is not None else {}
        frames: dict[str, ArmHandFrame] = {}

        for s in self.sides:
            st = self._states[s]
            pts: np.ndarray | None = None
            conf = 0.0
            hand_fresh = False

            pose_ok = det.pose_world is not None and det.pose_visibility is not None and \
                float(det.pose_visibility[list(POSE_IDX[s])].min()) >= self.min_visibility
            if pose_ok:
                arm = det.pose_world[list(POSE_IDX[s])] - origins[s]  # đổi gốc về vai
                vis = float(det.pose_visibility[list(POSE_IDX[s])].min())
                hand = self.matched.get(s)
                hand_rel: np.ndarray | None = None
                if hand is not None:
                    # Tịnh tiến bàn tay để điểm 0 trùng cổ tay của pose
                    hand_rel = hand.world - hand.world[0]
                    st.last_hand_rel, st.last_hand_t = hand_rel, t
                    conf = min(vis, hand.score)
                    hand_fresh = True
                elif st.last_hand_rel is not None and t - st.last_hand_t <= self.hold_time:
                    # Tạm mất bàn tay: giữ hình dạng cũ, bám theo cổ tay mới
                    hand_rel = st.last_hand_rel
                    conf = 0.5 * vis
                if hand_rel is not None:
                    pts = np.vstack([arm, arm[WRIST] + hand_rel])

            if pts is not None:
                if not st.valid:
                    st.filter.reset()  # vừa tìm lại tay -> không nội suy từ vị trí cũ
                pts = st.filter(pts, t)
                st.last_points, st.last_conf, st.valid = pts, conf, True
                if hand_fresh:  # chỉ phát hiện đầy đủ mới làm mới mốc giữ (tổng thời gian giữ ≤ hold_time)
                    st.last_good_t = t
                frames[s] = ArmHandFrame.from_points(pts, t, conf, True, s)
            elif st.last_points is not None and t - st.last_good_t <= self.hold_time:
                # Mất dấu ngắn: giữ giá trị cuối
                frames[s] = ArmHandFrame.from_points(st.last_points, t, st.last_conf, True, s)
            else:
                st.valid = False
                if st.last_points is not None:
                    last = st.last_points
                else:  # chưa từng thấy tay: dùng tư thế tham chiếu (vai lệch ±18 cm khi gốc ở giữa hai vai)
                    offset = (0.18 if s == "left" else -0.18) if len(self.sides) == 2 else 0.0
                    last = canonical_points(s) + np.array([offset, 0.0, 0.0])
                frames[s] = ArmHandFrame.from_points(last, t, 0.0, False, s)
        return frames
