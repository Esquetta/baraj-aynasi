"""Read clipped Sentinel-2 chips (B03, B08, SCL) for each dam box and cache them locally."""

import csv
import json
import threading
from pathlib import Path

import numpy as np
import planetary_computer
import pystac
import rasterio
from pyproj import Transformer
from rasterio.windows import Window, from_bounds

from .dams import Dam
from .water import clear_mask

CRS = "EPSG:32635"  # all three tiles are in UTM zone 35N
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "3",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
}


def utm_bounds(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """WGS84 box to UTM 35N bounds (densified edges)."""
    tr = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    return tr.transform_bounds(*box, densify_pts=21)


def scl_window(box, transform20) -> Window:
    """Integer 20 m window that covers the box; the 10 m window is exactly twice it."""
    w = from_bounds(*utm_bounds(box), transform=transform20)
    col0, row0 = int(np.floor(w.col_off)), int(np.floor(w.row_off))
    col1, row1 = int(np.ceil(w.col_off + w.width)), int(np.ceil(w.row_off + w.height))
    return Window(col0, row0, col1 - col0, row1 - row0)


def double(w: Window) -> Window:
    return Window(w.col_off * 2, w.row_off * 2, w.width * 2, w.height * 2)


def upsample2(a: np.ndarray) -> np.ndarray:
    """Nearest-neighbour 20 m -> 10 m."""
    return a.repeat(2, axis=0).repeat(2, axis=1)


class ChipStore:
    """data/chips/<dam>/<item id>.npz plus a per-tile index of every item looked at."""

    FIELDS = ("item_id", "datetime", "baseline", "dam", "clear_box", "saved")

    def __init__(self, root: Path, tile: str):
        self.root = root
        self.index_path = root / f"index_{tile}.csv"
        self.lock = threading.Lock()
        self.done: set[str] = set()
        if self.index_path.exists():
            with self.index_path.open(encoding="utf-8") as f:
                self.done = {row["item_id"] for row in csv.DictReader(f)}

    def chip_path(self, dam: str, item_id: str) -> Path:
        return self.root / dam / f"{item_id}.npz"

    def record(self, rows: list[dict]) -> None:
        with self.lock:
            new = not self.index_path.exists()
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            with self.index_path.open("a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self.FIELDS)
                if new:
                    w.writeheader()
                w.writerows(rows)
            self.done.update(r["item_id"] for r in rows)


def write_grids(root: Path, dams: list[Dam], item: pystac.Item) -> None:
    """Store each dam's chip grids (UTM transform per box) so masks can be rasterised later."""
    signed = planetary_computer.sign(item)
    with rasterio.Env(**GDAL_ENV), rasterio.open(signed.assets["SCL"].href) as scl:
        for dam in dams:
            grids = []
            for box in dam.boxes:
                w10 = double(scl_window(box, scl.transform))
                t10 = scl.transform * scl.transform.scale(0.5)
                t = rasterio.windows.transform(w10, t10)
                grids.append({"transform": list(t)[:6], "height": int(w10.height), "width": int(w10.width)})
            path = root / dam.key / "grid.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"crs": CRS, "boxes": grids}), encoding="utf-8")


def fetch_item(item: pystac.Item, dams: list[Dam], store: ChipStore, min_clear: float) -> list[dict]:
    """Read SCL for every dam box; when clear enough, read B03/B08 and save the chip."""
    signed = planetary_computer.sign(item)
    baseline = item.properties["s2:processing_baseline"]
    rows, keep = [], {}
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(signed.assets["SCL"].href) as src:
            for dam in dams:
                wins = [scl_window(b, src.transform) for b in dam.boxes]
                scls = [src.read(1, window=w) for w in wins]
                n = sum(s.size for s in scls)
                clear = sum(np.count_nonzero(clear_mask(s)) for s in scls) / n
                rows.append(
                    {
                        "item_id": item.id,
                        "datetime": item.properties["datetime"],
                        "baseline": baseline,
                        "dam": dam.key,
                        "clear_box": round(clear, 4),
                        "saved": clear >= min_clear,
                    }
                )
                if clear >= min_clear:
                    keep[dam.key] = (wins, scls)
        if keep:
            bands = {}
            for name in ("B03", "B08"):
                with rasterio.open(signed.assets[name].href) as src:
                    for key, (wins, _) in keep.items():
                        bands[(key, name)] = [src.read(1, window=double(w)) for w in wins]
            for key, (wins, scls) in keep.items():
                arrays = {"baseline": np.array(baseline), "datetime": np.array(item.properties["datetime"])}
                for j, s in enumerate(scls):
                    arrays[f"scl_{j}"] = s
                    arrays[f"b03_{j}"] = bands[(key, "B03")][j]
                    arrays[f"b08_{j}"] = bands[(key, "B08")][j]
                path = store.chip_path(key, item.id)
                path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(path, **arrays)
    return rows


def load_chip(path: Path) -> dict:
    with np.load(path) as z:
        return {k: z[k] for k in z.files}
