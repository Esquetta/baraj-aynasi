import json

import pandas as pd

from baraj_aynasi.iski import match_nearest, one_per_scene, parse_daily_summary, parse_page_windows, pick_by_priority


def test_match_nearest_within_window():
    scenes = pd.Series(pd.to_datetime(["2025-01-01", "2025-01-05", "2025-01-10"]))
    obs = pd.Series(pd.to_datetime(["2025-01-04", "2025-01-03", "2025-01-08", "2025-01-20"]))
    # 01-03 is two days from both 01-01 and 01-05: no match within one day.
    assert match_nearest(scenes, obs, max_days=1).tolist() == [1, -1, -1, -1]
    assert match_nearest(scenes, obs, max_days=2).tolist() == [1, 0, 2, -1]


def test_match_nearest_without_scenes():
    assert match_nearest(pd.Series([], dtype="datetime64[ns]"), pd.Series(pd.to_datetime(["2025-01-01"])), 1).tolist() == [-1]


def test_parse_daily_summary(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"data": [{"baraj": "BCekmece", "tarih": "25.10.2025", "yuzde": 27.69}]}), encoding="utf-8")
    df = parse_daily_summary(p)
    assert df.iloc[0].to_dict() == {
        "dam": "buyukcekmece",
        "date": pd.Timestamp("2025-10-25"),
        "occupancy_pct": 27.69,
        "source": "daily_summary",
    }


def test_parse_page_windows(tmp_path):
    p = tmp_path / "live.json"
    p.write_text(
        json.dumps(
            {
                "Omerli": {
                    "ayson": [{"dolulukOrani": 17.88, "tarih": "31.10.2025"}],
                    "ondort": [{"dolulukOrani": 79.47, "tarih": "28.10.2026"}],
                    "onyil": [{"oran": 41.43, "tarih": "28.10.2016"}],
                }
            }
        ),
        encoding="utf-8",
    )
    df = parse_page_windows(p)
    assert df.source.tolist() == ["month_end", "last_14_days", "same_day_10y"]
    assert df.dam.unique().tolist() == ["omerli"]
    assert df.occupancy_pct.tolist() == [17.88, 79.47, 41.43]


def test_pick_by_priority():
    obs = pd.DataFrame(
        {
            "dam": ["omerli", "omerli", "omerli"],
            "date": pd.to_datetime(["2026-10-28", "2026-10-28", "2026-10-27"]),
            "occupancy_pct": [79.0, 80.0, 77.0],
            "source": ["month_end", "last_14_days", "month_end"],
        }
    )
    out = pick_by_priority(obs, ["last_14_days", "month_end"])
    assert out.occupancy_pct.tolist() == [77.0, 80.0]


def test_one_per_scene_keeps_closest_iski_day():
    pairs = pd.DataFrame(
        {
            "dam": ["omerli"] * 3,
            "iski_date": ["2026-10-21", "2026-10-22", "2026-10-23"],
            "scene_date": ["2026-10-22"] * 3,
            "iski_pct": [77.47, 77.55, 77.47],
        }
    )
    out = one_per_scene(pairs)
    assert out.iski_date.tolist() == ["2026-10-22"] and out.gap_days.tolist() == [0]
