"""İBB daily dam occupancy (ground truth up to 2024-02-19)."""

from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd

URL = (
    "https://data.ibb.gov.tr/dataset/86658ecd-f3f7-4ca4-a313-ae6204f21959/resource/"
    "af0b3902-cfd9-4096-85f7-e2c3017e4f21/download/istanbul-dams-daily-occupancy-rates.xlsx"
)
END = pd.Timestamp("2024-02-19")


def load(cache: Path = Path("data/ibb/istanbul-dams-daily-occupancy-rates.xlsx")) -> pd.DataFrame:
    """Tidy frame: date, ibb_column, occupancy_pct (0-100)."""
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(URL, cache)
    wide = pd.read_excel(cache)
    wide = wide.rename(columns={wide.columns[0]: "date"})
    # Rows from 2023-04-01 to 2023-08-08 hold "d.m.yyyy" text dates and percentages;
    # every other row holds datetimes and fractions.
    wide["date"] = wide["date"].map(
        lambda v: pd.to_datetime(v, format="%d.%m.%Y") if isinstance(v, str) else pd.Timestamp(v)
    ).dt.normalize()
    values = wide.drop(columns="date").apply(pd.to_numeric, errors="coerce")
    as_percent = values.max(axis=1) > 1.5
    values[~as_percent] *= 100.0
    wide = pd.concat([wide[["date"]], values], axis=1)
    tidy = wide.melt(id_vars="date", var_name="ibb_column", value_name="occupancy_pct")
    tidy["ibb_column"] = tidy["ibb_column"].map(ascii_column)
    return tidy.dropna(subset=["occupancy_pct"]).sort_values(["ibb_column", "date"], ignore_index=True)


def ascii_column(name: str) -> str:
    """'Büyükçekmece' -> 'Buyukcekmece', matching the API column names used in dams.py."""
    return name.translate(str.maketrans("ÖöÇçĞğİıŞşÜü", "OoCcGgIiSsUu"))
