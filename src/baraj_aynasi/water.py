"""Pure raster functions: reflectance harmonisation, cloud mask, NDWI, water area."""

import numpy as np

# Scene classification (SCL) classes that hide the surface:
# 0 no data, 1 saturated/defective, 3 cloud shadow, 8/9 cloud, 10 cirrus, 11 snow.
SCL_INVALID = (0, 1, 3, 8, 9, 10, 11)


def boa_offset(processing_baseline: str) -> int:
    """Digital-number offset to add before scaling to reflectance.

    Baseline 04.00 (from January 2022, and reprocessed older items) stores
    reflectance with a +1000 offset. Decide by baseline, not by date, because
    the archive mixes baselines for the same dates.
    """
    major, minor = (int(p) for p in processing_baseline.split("."))
    return -1000 if (major, minor) >= (4, 0) else 0


def reflectance(dn: np.ndarray, offset: int) -> np.ndarray:
    """Surface reflectance from L2A digital numbers; DN 0 is no data (NaN)."""
    out = (dn.astype(np.float32) + offset) / 10000.0
    out[dn == 0] = np.nan
    return out


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """McFeeters NDWI = (G - NIR) / (G + NIR); NaN where undefined."""
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (green - nir) / (green + nir)
    out[~np.isfinite(out) | ((green + nir) <= 0)] = np.nan
    return out


def clear_mask(scl: np.ndarray) -> np.ndarray:
    """True where the SCL class does not hide the surface."""
    return ~np.isin(scl, SCL_INVALID)


def water_mask(index: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    """True where the water index is above the threshold (NaN is never water)."""
    with np.errstate(invalid="ignore"):
        return index > threshold


def water_area_km2(water: np.ndarray, aoi: np.ndarray, pixel_size_m: float = 10.0) -> float:
    """Water area inside the AOI in km2."""
    return float(np.count_nonzero(water & aoi)) * pixel_size_m**2 / 1e6


def clear_fraction(valid: np.ndarray, aoi: np.ndarray) -> float:
    """Share of AOI pixels that are observed (cloud-free, with data)."""
    n = np.count_nonzero(aoi)
    return float(np.count_nonzero(valid & aoi)) / n if n else 0.0
