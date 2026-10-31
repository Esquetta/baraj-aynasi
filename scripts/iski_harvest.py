"""Save the occupancy windows İSKİ's public page shows today, for every reservoir.

Opens https://iski.istanbul/baraj-doluluk/ in a headless browser like a
visitor, declines non-essential cookies, selects each reservoir in the detail
tab and reads what the page displays: month ends for the last year, the last
14 days, and today's date in each of the last ten years. Run once a day; over a
year the ten-year window fills in every calendar day of 2024-2026.

    uv run --extra harvest python scripts/iski_harvest.py

Writes data/iski/live_<date>.json (same shape scripts/iski_check.py reads).
"""

import datetime as dt
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from baraj_aynasi.iski import DAM_KEYS

URL = "https://iski.istanbul/baraj-doluluk/"
OUT = Path("data/iski")

# Reads the chart component's state for the reservoir selected in the detail tab.
READ_STATE = """(name) => {
  const found = [];
  (function walk(vm) {
    if (vm.$data && 'sonOnYildakiDolulukOrani' in vm.$data) found.push(vm);
    for (const c of vm.$children) walk(c);
  })(window.$nuxt);
  const vm = found.find((v) => v.$data.selectValue === name);
  if (!vm) return null;
  const d = vm.$data;
  return { ayson: d.sonBirYildakiAySonuDolulukOranlari, onyil: d.sonOnYildakiDolulukOrani, ondort: d.sonOnDortGundekiSu };
}"""


def harvest() -> dict:
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="tr-TR")
        page.goto(URL, wait_until="networkidle")
        decline = page.get_by_role("button", name="Reddet")
        if decline.count():
            decline.first.click()
        page.get_by_text("BARAJ DETAY GRAFİKLERİ").click()
        select = page.locator("select").filter(has=page.locator("option[value='Omerli']"))
        for name in DAM_KEYS:
            select.select_option(name)
            page.wait_for_function(
                "(name) => { let ok = false; (function w(vm){ if (vm.$data && vm.$data.selectValue === name"
                " && (vm.$data.sonOnYildakiDolulukOrani || []).length) ok = true; vm.$children.forEach(w); })(window.$nuxt); return ok; }",
                arg=name,
                timeout=30_000,
            )
            page.wait_for_timeout(1500)  # let the three per-reservoir requests settle
            state = page.evaluate(READ_STATE, name)
            if not state or not all(state.values()):
                raise RuntimeError(f"no data shown for {name}")
            out[name] = state
        browser.close()
    return out


def main() -> int:
    today = dt.date.today().isoformat()
    path = OUT / f"live_{today}.json"
    if path.exists():
        print(f"{path} already exists")
        return 0
    data = harvest()
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    days = {r["tarih"] for d in data.values() for r in d["onyil"]}
    print(f"wrote {path}: {len(data)} reservoirs, ten-year window {sorted(days)[0]}..{sorted(days)[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
