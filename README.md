# AIDAMS Lab 1 — Steel Plants & Socio-Economic Exposure

Geospatial analysis of the Global Iron and Steel Tracker, enriched with LitPop
exposure data, plus a Streamlit dashboard.

**Group:** Ben Njima · Gueddas · Mallat · Sanver · Tanaci
**Repo:** https://github.com/Jawadmallat/aidams-lab1-bennjima-gueddas-mallat-sanver-tanaci
**Streamlit Cloud:** _TODO — paste deployed URL_

---

## Quickstart

```bash
uv sync                          # create .venv and install dependencies
uv run jupyter lab lab_1.ipynb   # run the notebook (writes data/processed/)
uv run streamlit run app.py      # launch the dashboard
```

> Run the notebook **before** the dashboard: Part 6 writes the files `app.py` reads.

## Data (not committed — see `.gitignore`)

| Folder | Contents | Source |
|---|---|---|
| `gem-data/` | Global Iron and Steel Tracker, June 2026 V1 (`.xlsx`) | [Global Energy Monitor](https://globalenergymonitor.org/projects/global-iron-steel-tracker) |
| `litpop/` | LitPop 300 arcsec, CHN/IND/JPN (`.hdf5`) | Moodle sample / [ETH Research Collection](https://www.research-collection.ethz.ch/entities/researchdata/12dcfc4f-9d03-463a-8d6b-76c0dc73cdc8) |

Place the files in those folders to reproduce.

## What the notebook does

- **Part 1–2 — Load & EDA.** Merges the `Plant data` and `Plant capacities and status`
  sheets on `GEM plant ID`; parses the `"lat, lon"` string; coerces text sentinels
  (`'unknown'`, `'>0'`). 1,293 plants, 2.23 Gt/yr operating capacity.
- **Part 3 — Maps.** Scatter, capacity-sized and density maps (open basemaps, no token).
- **Part 4 — LitPop merge.** Reads CLIMADA HDF5 via `h5py`; nearest-cell match with a
  haversine `BallTree`, plus exposure summed within 25 km. 613 plants matched,
  median match distance 3.5 km.
- **Part 5 — Company aggregation.** Per-owner capacity, spread and exposure, including a
  capacity-weighted exposure; representative location from spherical centroid / largest plant.
- **Part 6 — Exports.** Writes `data/processed/*.{parquet,csv}` + `metadata.csv`.

## Scope note

LitPop samples cover **China, India and Japan only**. Parts 1–3 use all **1,293** plants;
**Parts 4–5 and the dashboard's exposure views use the 613 plants** in those countries, so
every exposure statistic rests on complete data.

`litpop_value_usd` is **produced capital in USD (2018)** — an asset-value proxy, *not* a
population count.

## Dashboard (`app.py`)

Sidebar filters (dataset → region → country → company → capacity) feed four tabs: **Map**
(colour by region/country/owner or exposure, plus density), **Exploration** (capacity,
age, capacity-vs-exposure), **Companies**, **Data** (table + CSV download).

## Notes / TODO

- [ ] Paste the Streamlit Cloud URL above and in the submission email
- [ ] `Owner` is free text — subsidiaries split company totals; `Parent (English)` would consolidate
- [ ] Raw data is currently tracked in git history (see below)

## Reproducibility

Python 3.13 · dependencies pinned in `pyproject.toml` / `uv.lock` · `data/processed/` is
committed so the dashboard runs on Streamlit Cloud without the raw inputs.
