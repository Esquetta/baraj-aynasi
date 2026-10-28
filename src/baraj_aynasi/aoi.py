"""Area-of-interest masks: the reservoir's high-water extent plus a margin."""

import numpy as np
from scipy import ndimage


def disk(radius_px: int) -> np.ndarray:
    y, x = np.ogrid[-radius_px : radius_px + 1, -radius_px : radius_px + 1]
    return x * x + y * y <= radius_px * radius_px


def reservoir_mask(
    water_freq: np.ndarray, seeds: list[tuple[int, int]], min_freq: float = 0.5, snap_px: int = 15
) -> np.ndarray:
    """Connected water components (8-neighbour) that contain the seed pixels (row, col).

    A seed off the water snaps to the nearest water pixel within `snap_px`,
    since seeds are picked by eye on narrow arms.
    """
    water = water_freq >= min_freq
    labels, _ = ndimage.label(water, structure=np.ones((3, 3), bool))
    dist, (near_r, near_c) = ndimage.distance_transform_edt(~water, return_indices=True)
    dry = [(r, c) for r, c in seeds if dist[r, c] > snap_px]
    if dry:
        raise ValueError(f"seed pixels not on water: {dry}")
    return np.isin(labels, [labels[near_r[r, c], near_c[r, c]] for r, c in seeds])


def aoi_mask(reservoir: np.ndarray, other_water: np.ndarray, margin_px: int) -> np.ndarray:
    """Reservoir grown by a margin, minus water bodies that are not the reservoir."""
    grown = ndimage.binary_dilation(reservoir, structure=disk(margin_px))
    return grown & ~(other_water & ~reservoir)
