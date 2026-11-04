import pandas as pd

from baraj_aynasi.health import (
    iski_stale,
    page_differs,
    plan,
    recent_error,
    update_unhealthy,
)

TODAY = pd.Timestamp("2026-11-04")


def test_iski_stale_after_two_days():
    series = pd.DataFrame({"dam": "x", "date": pd.to_datetime(["2026-10-01", "2026-11-02"])})
    assert iski_stale(series, TODAY) == {}
    assert list(iski_stale(series, TODAY + pd.Timedelta(days=1))) == ["İSKİ figures have stopped updating"]


def test_iski_stale_when_one_reservoir_stops():
    series = pd.DataFrame({"dam": ["x", "y"], "date": pd.to_datetime(["2026-11-04", "2026-10-20"])})
    assert iski_stale(series, TODAY)


def test_update_unhealthy_failed_missing_or_old():
    ok = {"conclusion": "success", "createdAt": "2026-11-03T12:55:25Z", "url": "u"}
    assert update_unhealthy(ok, TODAY) == {}
    assert update_unhealthy({**ok, "conclusion": ""}, TODAY) == {}  # still running
    assert update_unhealthy(None, TODAY)
    for conclusion in ("failure", "timed_out", "cancelled"):
        assert conclusion in next(iter(update_unhealthy({**ok, "conclusion": conclusion}, TODAY).values()))
    assert update_unhealthy({**ok, "createdAt": "2026-10-30T12:00:00Z"}, TODAY)


def test_page_differs_ignores_line_endings_only():
    assert page_differs("u", b"a\r\nb", b"a\nb") == {}
    assert page_differs("u", b"a\nb", b"a\nc")


def _pairs(errors):
    dates = pd.date_range("2026-01-01", periods=len(errors), freq="10D").strftime("%Y-%m-%d")
    return pd.DataFrame({"dam": "x", "iski_date": dates, "iski_pct": 50.0, "estimate_pct": [50.0 + e for e in errors]})


def test_recent_error_uses_only_the_latest_pairs():
    # Old misses have passed out of the window; misses in both directions count.
    assert recent_error(_pairs([40, 40, 2, -2, 2, -2, 2]), {"x": "X"}) == {}
    assert list(recent_error(_pairs([0, 0, 20, -20, 20, -20, 20]), {"x": "X"})) == ["Recent error above the stop line: X"]


def test_recent_error_exactly_on_the_line_is_not_a_problem():
    assert recent_error(_pairs([10, 10, 10, 10, 10]), {"x": "X"}) == {}


def test_recent_error_without_pairs_is_a_problem():
    # Only the named reservoir counts: x's large error here is not Other's.
    found = recent_error(_pairs([50] * 5), {"other": "Other"})
    assert "no comparisons" in found["Recent error above the stop line: Other"]


def test_plan_keeps_issues_whose_check_did_not_run():
    issues = [{"number": 1, "title": "Live page differs from main: u"}, {"number": 2, "title": "gone"}]
    assert plan({}, issues, ("Live page differs from main",)) == ([], [2])
    assert plan({}, issues) == ([], [1, 2])


def test_plan_opens_new_and_closes_cleared():
    issues = [{"number": 1, "title": "kept"}, {"number": 2, "title": "gone"}]
    assert plan({"kept": "b", "new": "b"}, issues) == (["new"], [2])
    assert plan({}, []) == ([], [])
