"""Synthetic full-arm image landmarks for TV1 runners and regression checks."""

from contracts import HandSample


def make_sample(frame_id, captured_at, processed_at, valid=True, u=.5, v=.5, ratio=.8,
                side="Right", width=640, height=480):
    # Keep the fixture visible even for control points outside the image rect.
    x = max(.1, min(.9, u))
    y = max(.1, min(.9, v))
    points = [(x, y-.025, 0.0)] * 21
    points[0] = (x, y+.1, 0.0)
    points[9] = (x, y-.1, 0.0)
    points[5] = points[13] = points[17] = (x, y, 0.0)
    # The average of wrist and four MCP joints is exactly (x, y).
    delta = ratio * .2 * height / width
    points[4], points[8] = (x-delta/2, y, 0.0), (x+delta/2, y, 0.0)
    arm = {"shoulder": (x, max(0, y-.18), 0.0, 1.0, 1.0),
           "elbow": (x, y-.04, 0.0, 1.0, 1.0),
           "wrist": (*points[0], 1.0, 1.0)}
    return HandSample(frame_id, captured_at, processed_at, valid, side, arm,
                      tuple(points), True, True, width, height)
