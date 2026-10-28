# Baraj Aynası

Satellite estimates, with error bars, of how full Istanbul's ten supply
reservoirs are. The water surface of each reservoir is measured in Sentinel-2
L2A imagery (2017–2026), and a per-reservoir curve maps surface area to the
occupancy İBB reported daily until 2024-02-19. After that date the curves turn
satellite measurements alone into occupancy estimates.

Status: Phase 1 (data pipeline and NDWI baseline). A small U-Net for cloud
shadow, turbid water and shoreline vegetation comes later.

## How it works

1. `scripts/search.py` caches Sentinel-2 L2A STAC items for tiles 35TPF, 35TQF
   and 35TNG from Microsoft Planetary Computer.
2. `scripts/download.py` reads clipped B03, B08 and SCL chips for every reservoir
   and keeps scenes with at least 30% cloud-free pixels in the search box.
3. `scripts/draw_aoi.py` draws each reservoir's area of interest from its
   high-water extent (see [docs/data-sources.md](docs/data-sources.md)).
4. `scripts/areas.py` computes NDWI = (green − NIR) / (green + NIR) and counts
   water pixels (NDWI > 0, cloud-free per SCL) inside the AOI.
5. `scripts/fit.py` fits area-to-occupancy curves on scenes up to 2022-06-30,
   reports error on 2022-07-01 to 2024-02-19, and sizes a 90% error bar from
   leave-one-year-out residuals.

```bash
uv sync
uv run pytest
uv run python scripts/search.py
uv run python scripts/download.py
uv run python scripts/draw_aoi.py
uv run python scripts/areas.py
uv run python scripts/fit.py
```

Raw imagery is cached under `data/` (about 30 GB) and is not committed.

## Data and attribution

- Reservoir occupancy: [İBB Açık Veri Portalı](https://data.ibb.gov.tr/dataset/istanbul-barajlari-gunluk-doluluk-oranlari),
  İstanbul Büyükşehir Belediyesi, under the [İBB Open Data License](https://data.ibb.gov.tr/license).
  Atıf 4.0 Uluslararası (CC BY 4.0) kapsamında lisanslanan kamu sektörü bilgilerini içerir.
- Imagery: Contains modified Copernicus Sentinel data 2017–2026, accessed through
  the Microsoft Planetary Computer.

Details, terms and the AOI drawing method are in
[docs/data-sources.md](docs/data-sources.md). Code is MIT licensed.
