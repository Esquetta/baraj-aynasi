"""Reservoir registry.

Search boxes are WGS84 (lon_min, lat_min, lon_max, lat_max), padded about 1 km
around the OpenStreetMap water outline. They only bound the STAC search and
the AOI drawing step; the area itself is measured inside aoi/reservoirs.geojson.
Capacities are İSKİ's "azami biriktirme hacmi" (million m3).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dam:
    key: str
    name: str
    ibb_column: str
    capacity_mcm: float
    boxes: tuple[tuple[float, float, float, float], ...]
    # Per box, (lon, lat) points that lie on the reservoir at high water; picked
    # by eye from aoi/review/<dam>_freq.png and used to seed the AOI drawing.
    seeds: tuple[tuple[tuple[float, float], ...], ...] = ()


DAMS: tuple[Dam, ...] = (
    Dam(
        "omerli", "Ömerli", "Omerli", 235.371, ((29.275, 40.950, 29.480, 41.095),),
        (((29.375, 41.060), (29.355, 40.975)),),
    ),
    Dam(
        "darlik", "Darlık", "Darlik", 107.500, ((29.535, 41.045, 29.627, 41.122),),
        (((29.5853, 41.0910), (29.6118, 41.0554)),),
    ),
    Dam(
        "elmali", "Elmalı", "Elmali", 9.600, ((29.096, 41.052, 29.143, 41.090),),
        (((29.1209, 41.0746), (29.1076, 41.0752)),),
    ),
    Dam(
        "terkos", "Terkos", "Terkos", 162.241, ((28.475, 41.285, 28.680, 41.400),),
        (((28.570, 41.335), (28.530, 41.375)),),
    ),
    Dam(
        "alibey", "Alibey", "Alibey", 34.143, ((28.850, 41.098, 28.945, 41.170),),
        (((28.885, 41.146), (28.925, 41.110)),),
    ),
    Dam(
        "buyukcekmece", "Büyükçekmece", "Buyukcekmece", 148.943, ((28.505, 41.026, 28.600, 41.115),),
        (((28.560, 41.070), (28.575, 41.035)),),
    ),
    Dam(
        "sazlidere", "Sazlıdere", "Sazlidere", 88.730, ((28.640, 41.100, 28.765, 41.185),),
        (((28.6878, 41.1231), (28.6562, 41.1734), (28.7456, 41.1429), (28.7339, 41.1311)),),
    ),
    Dam(
        "kazandere", "Kazandere", "Kazandere", 17.424, ((28.000, 41.598, 28.080, 41.6345),),
        (((28.0495, 41.6174), (28.0204, 41.6227)),),
    ),
    Dam(
        "pabucdere", "Pabuçdere", "Pabucdere", 58.500, ((27.975, 41.6345, 28.075, 41.685),),
        (((28.0354, 41.6549),),),
    ),
    # Istrancalar is five small stream reservoirs reported as one figure:
    # Düzdere, Kuzuludere, Büyükdere (mapped in OSM as Çilingöz), Sultanbahçedere, Elmalıdere.
    Dam(
        "istrancalar",
        "Istrancalar",
        "Istrancalar",
        6.231,
        (
            (28.283, 41.462, 28.298, 41.476),
            (28.243, 41.475, 28.270, 41.494),
            (28.180, 41.512, 28.207, 41.537),
            (28.085, 41.570, 28.110, 41.592),
            (28.130, 41.574, 28.141, 41.586),
        ),
        (
            ((28.2909, 41.4688),),
            ((28.2577, 41.4849),),
            ((28.1985, 41.5231),),
            ((28.0989, 41.5815),),
            ((28.1368, 41.5809),),
        ),
    ),
)

BY_KEY = {d.key: d for d in DAMS}
LARGEST_FOUR = ("omerli", "terkos", "buyukcekmece", "darlik")


def search_box(dam: Dam) -> tuple[float, float, float, float]:
    """Union of a dam's boxes."""
    xs0, ys0, xs1, ys1 = zip(*dam.boxes)
    return min(xs0), min(ys0), max(xs1), max(ys1)
