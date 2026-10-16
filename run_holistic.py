"""
Pipeline dung MediaPipe Holistic (pose + 2 ban tay 21 keypoint trong 1 model):
  webcam/video -> vai-khuyu-co tay (3D world) + 21 keypoint moi ban tay (x, y, z tuong doi)
  -> loc One Euro -> muc gap 5 ngon (tinh bang 3D) + huong long ban tay
  -> trang thai cam/nam -> mo phong PyBullet.

Chay:
  python run_holistic.py --sim
  python run_holistic.py --source video.mp4 --sim
"""
import argparse, math, time
import cv2, numpy as np
import mediapipe as mp

HAND_EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
              (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16),
              (0, 17), (17, 18), (18, 19), (19, 20)]
FINGERS = [(1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20)]
# Holistic: "left" = tay trai cua nguoi (cung quy uoc voi Pose). Pose idx: vai, khuyu, co tay
ARM_IDX = {"L": (11, 13, 15), "R": (12, 14, 16)}


class OneEuro:
    def __init__(self, mincut=1.0, beta=0.05, dcut=1.0):
        self.mincut, self.beta, self.dcut = mincut, beta, dcut
        self.x = self.dx = self.t = None

    @staticmethod
    def _a(cut, dt):
        r = 2 * math.pi * cut * dt
        return r / (r + 1)

    def __call__(self, x, t):
        x = np.asarray(x, np.float32)
        if self.x is None:
            self.x, self.dx, self.t = x, np.zeros_like(x), t
            return x
        dt = max(t - self.t, 1e-3)
        dx = (x - self.x) / dt
        self.dx = self.dx + self._a(self.dcut, dt) * (dx - self.dx)
        cut = self.mincut + self.beta * np.abs(self.dx)
        self.x = self.x + self._a(cut, dt) * (x - self.x)
        self.t = t
        return self.x

    def reset(self):
        self.x = None


def finger_curls(P):
    """P: (21,3). Muc gap 0 (thang) .. 1 (nam chat) cho 5 ngon, tinh bang khoang cach 3D."""
    out = []
    for ch in FINGERS:
        pts = P[list(ch)]
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1).sum() + 1e-6
        ratio = np.linalg.norm(pts[-1] - pts[0]) / seg
        out.append(float(np.clip((1 - ratio) / 0.45, 0, 1)))
    return np.array(out)


def palm_frame(P_sim, side):
    """He truc ban tay trong sim: x = huong ngon tay, y = phia ngon cai, z sao cho -z la phia long ban tay."""
    f = P_sim[9] - P_sim[0]; f /= np.linalg.norm(f) + 1e-9
    l = P_sim[5] - P_sim[17]; l = l - (l @ f) * f; l /= np.linalg.norm(l) + 1e-9
    z = np.cross(f, l) * (1.0 if side > 0 else -1.0)
    return np.stack([f, l, z], 1)


def draw_hand(frame, P, w, h):
    px = (P[:, :2] * [w, h]).astype(int)
    for a, b in HAND_EDGES:
        cv2.line(frame, tuple(px[a]), tuple(px[b]), (0, 255, 0), 2)
    for q in px:
        cv2.circle(frame, tuple(q), 3, (0, 0, 255), -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--complexity", type=int, default=1)
    a = ap.parse_args()

    holistic = mp.solutions.holistic.Holistic(
        model_complexity=a.complexity, smooth_landmarks=True,
        min_detection_confidence=0.5, min_tracking_confidence=0.5)
    sim = None
    if a.sim:
        from sim_env import HandSim, to_sim
        sim = HandSim()

    f_arm = {s: OneEuro(1.0, 0.05) for s in ARM_IDX}
    f_hand = {s: OneEuro(1.5, 0.02) for s in ARM_IDX}
    f_curl = {s: OneEuro(1.0, 0.05) for s in ARM_IDX}
    last = {s: None for s in ARM_IDX}  # (curls, R) gan nhat de giu khi tay bi che

    cap = cv2.VideoCapture(int(a.source) if a.source.isdigit() else a.source)
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        t = time.time()
        res = holistic.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        hands = {"L": res.left_hand_landmarks, "R": res.right_hand_landmarks}

        if res.pose_landmarks and res.pose_world_landmarks:
            L, W = res.pose_landmarks.landmark, res.pose_world_landmarks.landmark
            for s, (si, ei, wi) in ARM_IDX.items():
                if min(L[i].visibility for i in (si, ei, wi)) < 0.5:
                    continue
                arm2d = np.array([[L[i].x * w, L[i].y * h] for i in (si, ei, wi)]).astype(int)
                for p0, p1 in ((0, 1), (1, 2)):
                    cv2.line(frame, tuple(arm2d[p0]), tuple(arm2d[p1]), (255, 160, 0), 3)
                for q in arm2d:
                    cv2.circle(frame, tuple(q), 6, (255, 100, 0), -1)

                side = 1 if s == "R" else -1
                if hands[s] is not None:
                    P = np.array([[q.x, q.y, q.z] for q in hands[s].landmark], np.float32)
                    P = f_hand[s](P.ravel(), t).reshape(21, 3)
                    draw_hand(frame, P, w, h)
                    P3 = P * [w, h, w]  # z cua MediaPipe cung ti le voi x -> ve pixel
                    curls = f_curl[s](finger_curls(P3), t)
                    if sim is not None:
                        # Doi huong 3D ban tay sang he sim (chi lay huong, bo qua ti le)
                        Ps = np.array([to_sim(q, (0, 0, 0)) for q in P3])
                        last[s] = (curls, palm_frame(Ps, side))
                if sim is not None and last[s] is not None:
                    w3 = f_arm[s](np.array([[W[i].x, W[i].y, W[i].z] for i in (si, ei, wi)]).ravel(), t).reshape(3, 3)
                    sh, el, wr = [to_sim(q) for q in w3]
                    sim.update(sh, el, wr, last[s][0], side=side, R=last[s][1])
                    if sim.grasping:
                        cv2.putText(frame, f"GRASP {s}", (10, 30 if s == "L" else 60),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow("holistic arm + hand", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break


if __name__ == "__main__":
    main()
