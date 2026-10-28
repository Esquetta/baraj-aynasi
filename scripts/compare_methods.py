"""One table comparing NDWI, MNDWI and U-Net water masks by occupancy error.

Reads the outputs of scripts/fit.py and scripts/iski_check.py for each method
and writes results/unet/comparison.csv.

    uv run python scripts/compare_methods.py
"""

from pathlib import Path

import pandas as pd

METHODS = {"ndwi": Path("results"), "mndwi": Path("results/unet/mndwi"), "unet": Path("results/unet/unet")}


def main() -> None:
    parts = []
    for method, folder in METHODS.items():
        held = pd.read_csv(folder / "heldout_metrics.csv")[
            ["dam", "n_test", "test_mae", "loyo_mae_2017_2024", "error_bar_90", "test_coverage_90"]
        ]
        iski = pd.read_csv(folder / "iski_metrics.csv")[["dam", "n", "mae"]].rename(columns={"n": "iski_pairs", "mae": "iski_mae"})
        parts.append(held.merge(iski, on="dam").assign(method=method))
    long = pd.concat(parts)
    wide = long.pivot(index="dam", columns="method", values=["n_test", "test_mae", "loyo_mae_2017_2024", "error_bar_90", "test_coverage_90", "iski_pairs", "iski_mae"])
    wide.columns = [f"{metric}_{method}" for metric, method in wide.columns]
    order = [d for d in pd.read_csv(METHODS["ndwi"] / "heldout_metrics.csv").dam]
    wide = wide.loc[order].round(2)
    wide.to_csv("results/unet/comparison.csv")
    print(wide[[c for c in wide.columns if c.startswith(("test_mae", "iski_mae"))]].to_string())


if __name__ == "__main__":
    main()
