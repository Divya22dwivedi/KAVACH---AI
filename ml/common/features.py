"""Image feature extraction shared by data-integrity and shift modules.

Feature vector (115 dims):
  - 8x8 grayscale thumbnail, flattened / 255            (64)
  - 16-bin normalized histogram per RGB channel          (48)
  - brightness, contrast, blur (Laplacian variance)       (3)
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def extract_features(image: Image.Image) -> np.ndarray:
    img = image.convert("RGB")
    arr = np.asarray(img, dtype=np.float32)

    thumb = np.asarray(img.convert("L").resize((8, 8), Image.LANCZOS),
                       dtype=np.float32).flatten() / 255.0

    hists = []
    for c in range(3):
        h, _ = np.histogram(arr[:, :, c], bins=16, range=(0, 255))
        hists.append(h / (h.sum() + 1e-9))
    hist = np.concatenate(hists).astype(np.float32)

    gray = np.asarray(img.convert("L"), dtype=np.float32)
    brightness = gray.mean() / 255.0
    contrast = gray.std() / 255.0
    lap = (np.roll(gray, 1, 0) + np.roll(gray, -1, 0)
           + np.roll(gray, 1, 1) + np.roll(gray, -1, 1)
           - 4 * gray)
    blur = float(np.clip(lap.var() / 5000.0, 0.0, 1.0))

    return np.concatenate(
        [thumb, hist,
         np.array([brightness, contrast, blur], dtype=np.float32)])


FEATURE_DIM = 115
