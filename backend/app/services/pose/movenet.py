"""MoveNet SinglePose Lightning (TFLite) pose backend + adapter to our landmark format.

MoveNet emits **17 COCO keypoints**; the rest of the app (biomechanics, reps,
scoring) consumes the **33-landmark MediaPipe layout** as a ``(33, 4)`` array of
``(x, y, z, visibility)`` in normalized image coords. This module is the *adapter*:
it runs MoveNet and remaps its 17 keypoints onto the 33-slot MediaPipe array so the
downstream pipeline is untouched.

Known gaps (MoveNet has no such keypoints — those slots stay NaN / visibility 0, and
the pipeline is already NaN-safe):
- feet: heel / foot_index  -> e.g. squat ``heels_lift`` won't fire
- hands: pinky / index / thumb -> e.g. bicep-curl wrist angle (uses ``index``) breaks
- mouth, inner/outer eye detail

MoveNet is 2D (no depth); ``z`` is set to 0. The biomechanics engine uses only x/y,
so this is inconsequential for angles/positions. Confidence -> visibility 1:1.
"""
from __future__ import annotations

import logging

import numpy as np

from app.services.pose.landmarks import NUM_LANDMARKS

logger = logging.getLogger("kinesis.pose")

# MoveNet (COCO-17) index -> MediaPipe (33) index. Keypoints MoveNet lacks are simply
# absent here and remain NaN in the output array.
_MOVENET_TO_MP = {
    0: 0,    # nose
    1: 2,    # left_eye  -> MediaPipe left_eye
    2: 5,    # right_eye -> MediaPipe right_eye
    3: 7,    # left_ear
    4: 8,    # right_ear
    5: 11,   # left_shoulder
    6: 12,   # right_shoulder
    7: 13,   # left_elbow
    8: 14,   # right_elbow
    9: 15,   # left_wrist
    10: 16,  # right_wrist
    11: 23,  # left_hip
    12: 24,  # right_hip
    13: 25,  # left_knee
    14: 26,  # right_knee
    15: 27,  # left_ankle
    16: 28,  # right_ankle
}


def keypoints_to_landmarks(kps: np.ndarray) -> np.ndarray:
    """Map MoveNet output ``(17, 3)`` of ``(y, x, score)`` in *original-frame*
    normalized coords onto a ``(33, 4)`` MediaPipe-layout array ``(x, y, z, vis)``.
    Unmapped slots stay NaN with visibility 0 (our "no detection" convention)."""
    out = np.full((NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
    out[:, 3] = 0.0
    for mn_idx, mp_idx in _MOVENET_TO_MP.items():
        y, x, score = kps[mn_idx]
        out[mp_idx] = (float(x), float(y), 0.0, float(score))
    return out


def _load_interpreter(model_path: str, num_threads: int):
    """Load a TFLite interpreter from whichever LiteRT runtime is installed."""
    Interpreter = None
    try:
        from ai_edge_litert.interpreter import Interpreter  # current LiteRT runtime
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter  # legacy standalone
        except ImportError:
            from tensorflow.lite import Interpreter  # heavy fallback
    kwargs = {"model_path": model_path}
    if num_threads and num_threads > 0:
        kwargs["num_threads"] = num_threads  # TFLite DOES honour this (unlike MediaPipe Tasks)
    interp = Interpreter(**kwargs)
    interp.allocate_tensors()
    return interp


class MoveNetBackend:
    """Runs MoveNet SinglePose Lightning and returns landmarks in MediaPipe layout.

    Exposes the same ``infer(rgb, ts_ms) -> (33, 4)`` / ``close()`` contract as the
    MediaPipe backend, so the decode loop is model-agnostic. MoveNet is stateless
    per frame, so ``ts_ms`` is ignored (no tracking)."""

    name = "movenet"

    def __init__(self, model_path: str, *, num_threads: int = 0) -> None:
        import cv2  # noqa: F401 — needed for the letterbox resize

        self._cv2 = cv2
        self._interp = _load_interpreter(model_path, num_threads)
        inp = self._interp.get_input_details()[0]
        out = self._interp.get_output_details()[0]
        self._in_index = inp["index"]
        self._out_index = out["index"]
        self._in_dtype = inp["dtype"]
        # Input is [1, H, W, 3]; Lightning is 192x192.
        _, self._in_h, self._in_w, _ = inp["shape"]
        logger.info(
            "movenet backend: model=%s input=%dx%d dtype=%s threads=%s",
            model_path.split("/")[-1], self._in_w, self._in_h,
            np.dtype(self._in_dtype).name, num_threads or "default",
        )

    def _letterbox(self, rgb: np.ndarray) -> tuple[np.ndarray, int, int]:
        """Resize preserving aspect into the model's square input, padding
        bottom-right with zeros. Returns (padded_input, new_w, new_h)."""
        h, w = rgb.shape[:2]
        scale = min(self._in_w / w, self._in_h / h)
        new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
        resized = self._cv2.resize(rgb, (new_w, new_h), interpolation=self._cv2.INTER_AREA)
        padded = np.zeros((self._in_h, self._in_w, 3), dtype=np.uint8)
        padded[:new_h, :new_w] = resized
        return padded, new_w, new_h

    def infer(self, rgb: np.ndarray, ts_ms: int = 0) -> np.ndarray:
        padded, new_w, new_h = self._letterbox(rgb)
        # Float models want normalized float32; the int8 SinglePose Lightning model
        # takes uint8 [0,255] (its input tensor dtype is uint8). If you swap in a model
        # whose input dtype is genuinely int8, apply its quantization params here.
        if np.dtype(self._in_dtype) == np.float32:
            inp = (padded.astype(np.float32) / 255.0)[None, ...]
        else:
            inp = padded.astype(self._in_dtype)[None, ...]
        self._interp.set_tensor(self._in_index, inp)
        self._interp.invoke()
        kps = self._interp.get_tensor(self._out_index).reshape(17, 3).copy()  # (y, x, score) in padded space
        # Un-pad: map padded-normalized coords back to the original frame's normalized
        # coords (padding is bottom-right, so offset is 0).
        kps[:, 0] = kps[:, 0] * self._in_h / new_h  # y
        kps[:, 1] = kps[:, 1] * self._in_w / new_w  # x
        return keypoints_to_landmarks(kps)

    def close(self) -> None:  # symmetry with the MediaPipe backend; nothing to free
        pass
