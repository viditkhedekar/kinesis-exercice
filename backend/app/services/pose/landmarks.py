"""MediaPipe Pose landmark names, sided-joint resolution, and skeleton edges.

MediaPipe Pose Landmarker emits 33 landmarks. We expose:
- ``LANDMARK_INDEX``: name -> index for every landmark
- ``SIDED``: generic joint name -> (left_index, right_index) so exercise configs
  can say "knee" and get left/right resolved automatically
- ``POSE_EDGES``: index pairs for drawing the skeleton overlay
"""
from __future__ import annotations

NUM_LANDMARKS = 33

LANDMARK_INDEX: dict[str, int] = {
    "nose": 0,
    "left_eye_inner": 1, "left_eye": 2, "left_eye_outer": 3,
    "right_eye_inner": 4, "right_eye": 5, "right_eye_outer": 6,
    "left_ear": 7, "right_ear": 8,
    "mouth_left": 9, "mouth_right": 10,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_pinky": 17, "right_pinky": 18,
    "left_index": 19, "right_index": 20,
    "left_thumb": 21, "right_thumb": 22,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
    "left_heel": 29, "right_heel": 30,
    "left_foot_index": 31, "right_foot_index": 32,
}

# Landmarks used to judge "is a person actually in frame?".
#
# Deliberately restricted to torso + limb joints that EVERY pose backend can
# produce. MoveNet (COCO-17) has no mouth/eye-detail/finger/foot landmarks, so
# those slots are permanently visibility 0 under that backend — averaging
# presence over all 33 slots caps the score at 17/33 = 0.52 even for a flawless
# detection, which made a good clip look like an empty one. Judging presence on
# the landmarks a backend can actually emit keeps the metric backend-agnostic.
#
# These are also the landmarks that matter for framing: eyes and fingertips
# never told us whether the body was in shot.
CORE_PRESENCE_LANDMARKS: tuple[int, ...] = (
    0,          # nose
    11, 12,     # shoulders
    13, 14,     # elbows
    15, 16,     # wrists
    23, 24,     # hips
    25, 26,     # knees
    27, 28,     # ankles
)

# Generic joint name -> (left index, right index)
SIDED: dict[str, tuple[int, int]] = {
    "shoulder": (11, 12),
    "elbow": (13, 14),
    "wrist": (15, 16),
    "index": (19, 20),
    "thumb": (21, 22),
    "hip": (23, 24),
    "knee": (25, 26),
    "ankle": (27, 28),
    "heel": (29, 30),
    "foot": (31, 32),
    "ear": (7, 8),
    "eye": (2, 5),
}

# Skeleton connections (subset that reads well as an overlay).
POSE_EDGES: list[list[int]] = [
    [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
    [11, 23], [12, 24], [23, 24],
    [23, 25], [25, 27], [27, 31], [27, 29],
    [24, 26], [26, 28], [28, 32], [28, 30],
    [0, 11], [0, 12],
]


def resolve(name: str, side: str | None = None) -> int:
    """Resolve a landmark name (optionally a generic sided joint) to an index.

    ``resolve("knee", "left")`` -> 25; ``resolve("left_hip")`` -> 23.
    """
    if side is not None and name in SIDED:
        return SIDED[name][0 if side == "left" else 1]
    if name in LANDMARK_INDEX:
        return LANDMARK_INDEX[name]
    raise KeyError(f"Unknown landmark: {name!r} (side={side!r})")
