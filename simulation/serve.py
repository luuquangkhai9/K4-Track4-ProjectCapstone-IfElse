"""Static scene and low-latency HTTP command bridge for the pick-cell simulation.

Run with: python simulation/serve.py [port]
The browser polls the latest command; a CPU-only controller can POST at camera rate.
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


ROOT = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()
LATEST = {"sequence": 0, "command": None}


def finite_point(value):
    if isinstance(value, dict):
        point = [value.get("x"), value.get("y"), value.get("z")]
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        point = value[:3]
    else:
        return None
    if any(isinstance(axis, bool) or not isinstance(axis, (int, float)) or not math.isfinite(axis) for axis in point):
        return None
    x, y, z = map(float, point)
    if not (-3.2 <= x <= 3.2 and 0.55 <= y <= 3.0 and -2.5 <= z <= 2.5):
        return None
    if math.sqrt(x * x + (y - 1.22) * (y - 1.22) + z * z) > 2.62:
        return None
    return {"x": x, "y": y, "z": z}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin")
        if origin and self._allowed_origin():
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def _allowed_origin(self):
        origin = self.headers.get("Origin")
        port = self.server.server_port
        return origin is None or origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

    def log_message(self, fmt, *args):
        pass

    def _json(self, status, data):
        body = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if not self._allowed_origin():
            self._json(403, {"error": "cross-origin control is not allowed"})
            return
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            bridge = getattr(self.server, "bridge", None)
            self._json(200, bridge.snapshot() if bridge else {"active": False})
            return
        if parsed.path == "/api/health":
            self._json(200, {"ready": True, "service": "robot-pick-cell"})
            return
        if parsed.path == "/api/command":
            try:
                after = int(parse_qs(parsed.query).get("after", ["0"])[0])
            except ValueError:
                self._json(400, {"error": "after must be an integer"})
                return
            with LOCK:
                snapshot = dict(LATEST)
            self._json(200, {"sequence": snapshot["sequence"], "command": snapshot["command"] if snapshot["sequence"] > after else None})
            return
        super().do_GET()

    def do_POST(self):
        global LATEST
        if not self._allowed_origin():
            self._json(403, {"error": "cross-origin control is not allowed"})
            return
        path = urlparse(self.path).path
        bridge = getattr(self.server, "bridge", None)
        if path not in ("/api/command", "/api/input"):
            self._json(404, {"error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 65536:
                raise ValueError("body must be between 1 and 65536 bytes")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            if path == "/api/input":
                if bridge is None:
                    self._json(409, {"error": "Start main.py --web for integrated control"})
                    return
                key = payload.get("key")
                if key not in ("p", "c", "r", "q", "t"):
                    raise ValueError("key must be p/c/r/q/t")
                bridge.input(key)
                self._json(202, {"accepted": True})
                return
            if bridge is not None:
                self._json(409, {"error": "Integrated mode uses controller commands only"})
                return
            target = finite_point(payload.get("target"))
            if target is None and isinstance(payload.get("keypoints"), dict):
                target = finite_point(payload["keypoints"].get("wrist"))
            if target is None and all(axis in payload for axis in ("x", "y", "z")):
                target = finite_point(payload)
            if target is None:
                raise ValueError("target must be finite and inside the robot workspace (within 2.62 m of the shoulder)")
            grip = payload.get("grip", payload.get("gripper", 0))
            if isinstance(grip, bool):
                grip = int(grip)
            if grip not in (0, 1):
                raise ValueError("grip must be 0 (open) or 1 (closed)")
            command = {"target": target, "grip": grip}
            with LOCK:
                LATEST = {"sequence": LATEST["sequence"] + 1, "command": command}
                sequence = LATEST["sequence"]
            self._json(202, {"accepted": True, "sequence": sequence, "command": command})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            self._json(400, {"accepted": False, "error": str(exc)})


class IntegrationBridge:
    """Only publishes snapshots; never touches PyBullet from HTTP worker threads."""
    def __init__(self, port=8765):
        self._lock = threading.Lock()
        self._state = {"active": True, "ready": False}
        self._key = None
        self._revision = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True
        self.server.bridge = self
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def publish(self, state):
        with self._lock:
            self._revision += 1
            self._state = dict(state, ready=True, revision=self._revision)

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def input(self, key):
        with self._lock:
            # Stop/reset have priority over repeated resume/start-trial clicks.
            if self._key not in ("q", "r") or key == "q":
                self._key = key

    def poll_key(self):
        with self._lock:
            key, self._key = self._key, None
            return key

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


if __name__ == "__main__":
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print(f"Robot Pick Cell sẵn sàng tại http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng simulation.")
    finally:
        server.server_close()
