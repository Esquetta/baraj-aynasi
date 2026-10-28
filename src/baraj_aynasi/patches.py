"""Training patches for the U-Net: model inputs and candidate water masks (pure functions)."""

import numpy as np

from .water import mndwi, ndwi

PATCH = 96  # pixels at 10 m, about 1 km across
CANDIDATES = ("ndwi", "mndwi", "union", "intersection", "dark_nir")


def input_stack(green: np.ndarray, red: np.ndarray, nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Model input, channels first: four reflectances, NDWI and MNDWI; NaN becomes 0.

    `swir` must already be on the 10 m grid.
    """
    x = np.stack([green, red, nir, swir, ndwi(green, nir), mndwi(green, swir)]).astype(np.float32)
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    """Threshold that best splits values into two classes (Otsu's method)."""
    v = values[np.isfinite(values)]
    hist, edges = np.histogram(v, bins=bins)
    mids = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * mids) / np.maximum(w0, 1)
    m1 = (np.sum(hist * mids) - np.cumsum(hist * mids)) / np.maximum(w1, 1)
    between = w0 * w1 * (m0 - m1) ** 2
    return float(mids[np.argmax(between)])


def candidate_masks(green: np.ndarray, nir: np.ndarray, swir: np.ndarray) -> dict[str, np.ndarray]:
    """Water masks a reviewer chooses between.

    Index masks use index > 0. `dark_nir` splits the patch's near-infrared at
    its Otsu threshold: open water stays darker than land in NIR even when
    algae push NDWI and MNDWI below zero, but the split is meaningless in a
    patch that is nearly all water or all land.
    """
    with np.errstate(invalid="ignore"):
        a = ndwi(green, nir) > 0
        b = mndwi(green, swir) > 0
        dark = nir < otsu_threshold(nir)
    return {"ndwi": a, "mndwi": b, "union": a | b, "intersection": a & b, "dark_nir": dark}


def sample_patch_origins(
    aoi: np.ndarray, water: np.ndarray, n: int, rng: np.random.Generator, size: int = PATCH, tries: int = 200
) -> list[tuple[int, int]]:
    """Top-left corners of up to n patches inside the chip, centred on AOI pixels.

    Patches that hold both water and land (15-85% water) are preferred, since
    the shoreline is where masks disagree; others are kept one time in five.
    """
    h, w = aoi.shape
    if h < size or w < size:
        return []
    rows, cols = np.nonzero(aoi)
    out: list[tuple[int, int]] = []
    for _ in range(tries):
        if len(out) == n or rows.size == 0:
            break
        k = rng.integers(rows.size)
        r0 = int(np.clip(rows[k] - size // 2, 0, h - size))
        c0 = int(np.clip(cols[k] - size // 2, 0, w - size))
        frac = water[r0 : r0 + size, c0 : c0 + size].mean()
        if 0.15 <= frac <= 0.85 or rng.random() < 0.2:
            out.append((r0, c0))
    return out
