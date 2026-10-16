"""
Moi truong mo phong 3D (PyBullet): hien thi canh tay + ban tay 21 khop theo keypoint bat duoc,
va mo phong hanh dong cam nam mot vat the.
"""
import numpy as np
import pybullet as p
import pybullet_data

HAND_EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
              (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16),
              (0, 17), (17, 18), (18, 19), (19, 20)]
# goc ngon (trong he toa do ban tay: x = huong cang tay, y = ngang, z = len)
BASES = [(0.02, 0.035, 0), (0.09, 0.028, 0), (0.095, 0.009, 0), (0.09, -0.01, 0), (0.08, -0.028, 0)]
SEGS = [(0.04, 0.03, 0.025), (0.045, 0.028, 0.022), (0.05, 0.03, 0.024),
        (0.047, 0.029, 0.023), (0.037, 0.022, 0.019)]
MAX_FLEX = (0.9, 1.4, 1.6, 1.2)  # thumb/index.. : goc gap toi da (rad) cho 3 khop


def to_sim(w, offset=(0.0, 0.0, 1.0)):
    """Toa do world cua MediaPipe (x phai, y xuong, z ra xa camera) -> sim (x phai, y sau, z len).
    Neu chieu bi nguoc, doi dau o day."""
    return np.array([w[0], w[2], -w[1]]) + np.array(offset)  # phep quay dung (khong lat guong)


class HandSim:
    def __init__(self, gui=True):
        p.connect(p.GUI if gui else p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.8)
        p.loadURDF("plane.urdf")
        p.resetDebugVisualizerCamera(1.4, 20, -25, [0, 0, 1.0])
        self.obj_start = np.array([0.0, -0.25, 0.75])
        self.table = p.createMultiBody(0, p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.3, 0.3, 0.35]),
                                       basePosition=[0, -0.25, 0.35])
        self.obj = p.createMultiBody(
            0.15, p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.03] * 3),
            p.createVisualShape(p.GEOM_BOX, halfExtents=[0.03] * 3, rgbaColor=[1, 0.3, 0.2, 1]),
            basePosition=self.obj_start.tolist())
        sph = lambda r, c: p.createMultiBody(0, -1, p.createVisualShape(p.GEOM_SPHERE, radius=r, rgbaColor=c),
                                             basePosition=[0, 0, -5])
        self.arm_pts = [sph(0.025, [0.2, 0.5, 1, 1]) for _ in range(3)]       # vai, khuyu, co tay
        self.hand_pts = [sph(0.008, [0.1, 0.9, 0.3, 1]) for _ in range(21)]
        self.arm_lines, self.hand_lines = [-1] * 2, [-1] * len(HAND_EDGES)
        self.grasping = False

    def _line(self, store, i, a, b, color):
        store[i] = p.addUserDebugLine(a, b, color, 3, replaceItemUniqueId=store[i])

    @staticmethod
    def hand_fk(wrist, elbow, curls, side=1, R=None):
        """21 diem ban tay trong sim tu co tay, khuyu va muc gap 5 ngon (0..1)."""
        if R is None:  # khong co huong long ban tay -> suy ra tu cang tay
            x = wrist - elbow; x /= np.linalg.norm(x) + 1e-9
            y = np.cross([0, 0, 1.0], x)
            if np.linalg.norm(y) < 1e-6:
                y = np.array([0, 1.0, 0])
            y /= np.linalg.norm(y)
            z = np.cross(x, y)
            R = np.stack([x, y * side, z], 1)  # cot = truc ban tay
        else:
            side = 1  # R (tu landmark ban tay) da chua san huong ngon cai
        pts = [wrist]
        for f in range(5):
            cur = np.array(BASES[f]) * np.array([1, side, 1])
            phi = 0.0
            for s in range(3):
                phi += curls[f] * MAX_FLEX[s + 1 if f else s]
                d = np.array([np.cos(phi), 0.0, -np.sin(phi)])
                if f == 0:  # ngon cai xoe ra ngoai
                    d = np.array([np.cos(phi) * 0.7, 0.7 * side, -np.sin(phi)])
                if s == 0:
                    pts.append(wrist + R @ cur)
                cur = cur + d * SEGS[f][s]
                pts.append(wrist + R @ cur)
        # pts: [0] + moi ngon 4 diem (goc, 3 khop) -> khop dung thu tu MediaPipe/CMU 1..20
        return np.array(pts)

    def update(self, shoulder, elbow, wrist, curls, side=1, R=None):
        """Cac tham so la vector 3D da o he sim. curls: 5 gia tri 0..1 (cai, tro, giua, ap ut, ut)."""
        for pid, q in zip(self.arm_pts, (shoulder, elbow, wrist)):
            p.resetBasePositionAndOrientation(pid, q.tolist(), [0, 0, 0, 1])
        self._line(self.arm_lines, 0, shoulder, elbow, [0.2, 0.5, 1])
        self._line(self.arm_lines, 1, elbow, wrist, [0.2, 0.5, 1])
        H = self.hand_fk(wrist, elbow, curls, side, R)
        for pid, q in zip(self.hand_pts, H):
            p.resetBasePositionAndOrientation(pid, q.tolist(), [0, 0, 0, 1])
        for i, (a, b) in enumerate(HAND_EDGES):
            self._line(self.hand_lines, i, H[a], H[b], [0.1, 0.9, 0.3])
        self._grasp_logic(H, float(np.mean(curls)))
        p.stepSimulation()

    def _grasp_logic(self, H, mean_curl):
        palm = (H[0] + H[9]) / 2
        obj_pos, _ = p.getBasePositionAndOrientation(self.obj)
        near = np.linalg.norm(palm - np.array(obj_pos)) < 0.12
        if not self.grasping and mean_curl > 0.6 and near:
            self.grasping = True
            p.changeDynamics(self.obj, -1, mass=0)  # giu vat theo tay
        elif self.grasping and mean_curl < 0.35:
            self.grasping = False
            p.changeDynamics(self.obj, -1, mass=0.15)  # tha vat
        if self.grasping:
            p.resetBasePositionAndOrientation(self.obj, (palm + [0, 0, -0.02]).tolist(), [0, 0, 0, 1])
