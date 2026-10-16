"""
Pipeline: webcam/video -> khung xuong canh tay (vai-khuyu-co tay) -> crop ban tay
-> 21 keypoint ban tay (model huan luyen tren CMU Panoptic Hand) -> tracking + loc
-> muc gap ngon / trang thai cam nam -> mo phong 3D PyBullet.

Chay:
  python run_pipeline.py --weights hand_net.pt --source 0 --sim
  python run_pipeline.py --weights hand_net.pt --source video.mp4
"""
import argparse, math, time
import cv2, numpy as np, torch
import mediapipe as mp
from train_hand import HandNet, decode, make_affine, to_tensor, HAND_EDGES, IN, HM

# chi so MediaPipe Pose: (vai, khuyu, co tay, ngon tro, ngon ut)
SIDES = {"L": (11, 13, 15, 19, 17), "R": (12, 14, 16, 20, 18)}
FINGERS = [(1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20)]


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


def finger_curls(kp):
    """Muc gap 0 (duoi thang) .. 1 (nam chat) cua 5 ngon, tu keypoint 2D."""
    out = []
    for ch in FINGERS:
        pts = kp[list(ch)]
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1).sum() + 1e-6
        ratio = np.linalg.norm(pts[-1] - pts[0]) / seg
        out.append(float(np.clip((1 - ratio) / 0.45, 0, 1)))
    return np.array(out)


class HandTracker:
    def __init__(self, net, dev):
        self.net, self.dev = net, dev
        self.kp = None            # keypoint frame truoc (anh goc) de crop theo vet
        self.f_kp = OneEuro(1.5, 0.02)
        self.f_curl = OneEuro(1.0, 0.05)
        self.lost = 0

    def crop_from_pose(self, wrist, index):
        d = np.linalg.norm(index - wrist)
        size = max(2.6 * d, 80)
        return wrist + 0.8 * (index - wrist), size

    @torch.no_grad()
    def __call__(self, rgb, wrist, index, t):
        if self.kp is not None and self.lost < 5:
            c = (self.kp.max(0) + self.kp.min(0)) / 2
            size = max((self.kp.max(0) - self.kp.min(0)).max() * 1.7, 64)
        else:
            c, size = self.crop_from_pose(wrist, index)
        M = make_affine(c, size)
        crop = cv2.warpAffine(rgb, M, (IN, IN))
        hm = self.net(to_tensor(crop)[None].to(self.dev))
        pred, conf = decode(hm)
        pred, conf = pred[0].cpu().numpy(), conf[0].cpu().numpy()
        Minv = cv2.invertAffineTransform(M)
        kp = pred @ Minv[:, :2].T + Minv[:, 2]
        if conf.mean() < 0.25:                     # mat dau -> quay lai crop theo pose
            self.lost += 1
            self.kp = None
            return None, None, conf
        self.lost = 0
        kp = self.f_kp(kp, t)
        self.kp = kp
        return kp, self.f_curl(finger_curls(kp), t), conf


def draw(frame, arm, kp):
    for a, b in ((0, 1), (1, 2)):
        cv2.line(frame, tuple(arm[a].astype(int)), tuple(arm[b].astype(int)), (255, 160, 0), 3)
    for q in arm:
        cv2.circle(frame, tuple(q.astype(int)), 6, (255, 100, 0), -1)
    if kp is not None:
        for a, b in HAND_EDGES:
            cv2.line(frame, tuple(kp[a].astype(int)), tuple(kp[b].astype(int)), (0, 255, 0), 2)
        for q in kp:
            cv2.circle(frame, tuple(q.astype(int)), 3, (0, 0, 255), -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--source", default="0")
    ap.add_argument("--sim", action="store_true")
    a = ap.parse_args()

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    net = HandNet(pretrained=False)
    net.load_state_dict(torch.load(a.weights, map_location=dev))
    net.to(dev).eval()
    pose = mp.solutions.pose.Pose(model_complexity=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)
    trackers = {s: HandTracker(net, dev) for s in SIDES}
    arm_f = {s: OneEuro(1.0, 0.05) for s in SIDES}
    sim = None
    if a.sim:
        from sim_env import HandSim, to_sim
        sim = HandSim()

    cap = cv2.VideoCapture(int(a.source) if a.source.isdigit() else a.source)
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        t = time.time()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)
        if res.pose_landmarks:
            h, w = frame.shape[:2]
            L = res.pose_landmarks.landmark
            W = res.pose_world_landmarks.landmark
            for s, (si, ei, wi, ii, pi) in SIDES.items():
                if min(L[i].visibility for i in (si, ei, wi)) < 0.5:
                    trackers[s].kp = None
                    continue
                px = lambda i: np.array([L[i].x * w, L[i].y * h], np.float32)
                arm2d = np.stack([px(si), px(ei), px(wi)])
                kp, curls, _ = trackers[s](rgb, px(wi), px(ii), t)
                draw(frame, arm2d, kp)
                if sim is not None and curls is not None:
                    w3 = arm_f[s](np.array([[W[i].x, W[i].y, W[i].z] for i in (si, ei, wi)]).ravel(), t).reshape(3, 3)
                    sh, el, wr = [to_sim(q) for q in w3]
                    sim.update(sh, el, wr, curls, side=1 if s == "R" else -1)
                    if sim.grasping:
                        cv2.putText(frame, f"GRASP {s}", (10, 30 if s == "L" else 60),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow("arm + hand tracking", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break


if __name__ == "__main__":
    main()
