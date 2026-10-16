"""Authoritative PyBullet scene; the Three.js scene can mirror snapshot()."""

from math import dist

from config import DEFAULT_CONFIG
from contracts import RobotCommand, SimStatus


class Simulation:
    def __init__(self, config=DEFAULT_CONFIG):
        self.config = config
        self.p = None
        self.constraint = None
        self.held = None
        self.placed = set()
        self._settled_since = {}
        self._time = self._remainder = 0.0

    def initialize(self):
        import pybullet
        import pybullet_data
        from pybullet_utils.bullet_client import BulletClient
        self.p = BulletClient(pybullet.GUI if self.config.simulation_gui else pybullet.DIRECT)
        self.p.setAdditionalSearchPath(pybullet_data.getDataPath())
        return self.reset()

    def reset(self):
        p, c = self.p, self.config
        p.resetSimulation()
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(1 / 240)
        p.setPhysicsEngineParameter(numSolverIterations=100)
        p.loadURDF("plane.urdf")
        self.robot = p.loadURDF("franka_panda/panda.urdf", useFixedBase=True)
        self.ee_link = 11
        self.orientation = p.getQuaternionFromEuler(c.downward_euler)
        for joint, value in enumerate((0, -0.5, 0, -2.2, 0, 1.8, 0.8)):
            p.resetJointState(self.robot, joint, value)
        self.target = c.home_xyz
        joints = p.calculateInverseKinematics(self.robot, self.ee_link, self.target,
                                              self.orientation, maxNumIterations=200,
                                              residualThreshold=1e-6)
        for joint in range(7):
            p.resetJointState(self.robot, joint, joints[joint])
        self.boxes = {}
        collision = p.createCollisionShape(p.GEOM_BOX, halfExtents=c.box_half_size)
        for box_id, xyz, rgb in c.boxes:
            visual = p.createVisualShape(p.GEOM_BOX, halfExtents=c.box_half_size, rgbaColor=(*rgb, 1))
            body = p.createMultiBody(0.08, collision, visual, xyz)
            p.changeDynamics(body, -1, lateralFriction=0.8)
            # Grasping is a fixed constraint, not a finger-contact simulation.
            # Prevent the decorative gripper from pushing boxes before attaching.
            for link in range(-1, p.getNumJoints(self.robot)):
                p.setCollisionFilterPair(self.robot, body, link, -1, 0)
            self.boxes[box_id] = body
        x, y = c.bin_center
        hx, hy = c.bin_half_size
        self._static_box((hx, hy, .005), (x, y, .005))
        for extent, position in (
            ((.005, hy, .03), (x - hx, y, .03)),
            ((.005, hy, .03), (x + hx, y, .03)),
            ((hx, .005, .03), (x, y - hy, .03)),
            ((hx, .005, .03), (x, y + hy, .03)),
        ):
            self._static_box(extent, position)
        self.constraint = self.held = None
        self.placed = set()
        self._settled_since = {}
        self._time = self._remainder = 0.0
        self._drive(RobotCommand(self.target, False))
        for _ in range(120):
            p.stepSimulation()
        p.resetDebugVisualizerCamera(1.2, 60, -40, (.5, 0, .1))
        self._highlighted = None
        return self.status()

    def _static_box(self, extent, position):
        p = self.p
        shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=extent)
        visual = p.createVisualShape(p.GEOM_BOX, halfExtents=extent, rgbaColor=(.2, .6, .6, 1))
        p.createMultiBody(0, shape, visual, position)

    def _drive(self, command):
        p = self.p
        self.target = command.target_xyz
        joints = p.calculateInverseKinematics(self.robot, self.ee_link, self.target,
                                              self.orientation, maxNumIterations=100,
                                              residualThreshold=1e-5)
        p.setJointMotorControlArray(self.robot, list(range(7)), p.POSITION_CONTROL,
                                   targetPositions=joints[:7], forces=[200] * 7,
                                   positionGains=[0.25] * 7)
        opening = .0 if command.gripper_closed else .04
        p.setJointMotorControlArray(self.robot, [9, 10], p.POSITION_CONTROL,
                                   targetPositions=[opening, opening], forces=[20, 20])

    def step(self, command, dt):
        if dt < 0:
            raise ValueError("dt must be nonnegative")
        self._drive(command)
        self._remainder += min(dt, self.config.max_control_dt)
        while self._remainder + 1e-12 >= 1 / 240:
            self.p.stepSimulation()
            self._time += 1 / 240
            self._remainder -= 1 / 240
        self._check_placed()
        return self.status()

    def _ee(self):
        state = self.p.getLinkState(self.robot, self.ee_link, computeForwardKinematics=True)
        return tuple(state[4])

    def status(self):
        ee = self._ee()
        eligible = [(dist(ee[:2], self.p.getBasePositionAndOrientation(body)[0][:2]), box_id)
                    for box_id, body in self.boxes.items()
                    if box_id not in self.placed and box_id != self.held]
        nearest = min(eligible, default=(float("inf"), None))
        candidate = nearest[1] if nearest[0] <= self.config.candidate_distance else None
        if candidate != self._highlighted:
            for box_id, _, rgb in self.config.boxes:
                color = (1, 1, .15) if box_id == candidate else rgb
                self.p.changeVisualShape(self.boxes[box_id], -1, rgbaColor=(*color, 1))
            self._highlighted = candidate
        return SimStatus(ee, dist(ee, self.target) <= self.config.position_tolerance,
                         candidate, self.held, frozenset(self.placed))

    def try_attach(self, box_id):
        if self.held is not None:
            return self.held == box_id
        if box_id not in self.boxes or box_id in self.placed:
            return False
        p, c = self.p, self.config
        ee = self._ee()
        box_pos, box_orn = p.getBasePositionAndOrientation(self.boxes[box_id])
        grasp = (ee[0], ee[1], ee[2] - c.grasp_offset)
        if dist(grasp, box_pos) > c.attach_distance:
            return False
        link = p.getLinkState(self.robot, self.ee_link, computeForwardKinematics=True)
        inv = p.invertTransform(link[4], link[5])
        offset, orientation = p.multiplyTransforms(*inv, box_pos, box_orn)
        self.constraint = p.createConstraint(self.robot, self.ee_link, self.boxes[box_id], -1,
                                             p.JOINT_FIXED, (0, 0, 0), offset, (0, 0, 0),
                                             parentFrameOrientation=orientation)
        p.changeConstraint(self.constraint, maxForce=500)
        self.held = box_id
        return True

    def release(self):
        if self.constraint is not None:
            self.p.removeConstraint(self.constraint)
        self.constraint = self.held = None

    def _check_placed(self):
        c = self.config
        for box_id, body in self.boxes.items():
            xyz, _ = self.p.getBasePositionAndOrientation(body)
            velocity, angular = self.p.getBaseVelocity(body)
            aabb = self.p.getAABB(body)
            inside = all(c.bin_center[i] - c.bin_half_size[i] + .005 <= aabb[0][i]
                         and aabb[1][i] <= c.bin_center[i] + c.bin_half_size[i] - .005
                         for i in (0, 1))
            settled = (box_id != self.held and inside and .015 <= xyz[2] <= .07
                       and dist(velocity, (0, 0, 0)) < .03
                       and dist(angular, (0, 0, 0)) < .1)
            if settled:
                since = self._settled_since.setdefault(box_id, self._time)
                if self._time - since >= .15:
                    self.placed.add(box_id)
            else:
                self._settled_since.pop(box_id, None)

    def snapshot(self):
        status = self.status()
        return {"ee_xyz": status.ee_xyz, "target_xyz": self.target,
                "candidate_box_id": status.candidate_box_id, "held_box_id": self.held,
                "placed_box_ids": sorted(self.placed),
                "boxes": {key: self.p.getBasePositionAndOrientation(body)[0]
                          for key, body in self.boxes.items()},
                "bin_center": self.config.bin_center, "active": True}

    def close(self):
        if self.p is not None:
            self.p.disconnect()
            self.p = None
