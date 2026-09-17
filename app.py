"""AIDAMS Lab 1 -- Global steel plants & LitPop exposure dashboard.

Run locally:
    uv run streamlit run app.py

Reads the precomputed exports written by lab_1.ipynb (Part 6) from
data/processed/. The heavy work -- parsing the GEM workbook and the LitPop
HDF5 grids, and the spatial join -- happens in the notebook, so this app only
loads three small Parquet files and stays responsive.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path(__file__).parent / "data" / "processed"
MAP_STYLE = "open-street-map"  # no Mapbox token required
NEIGHBOURHOOD_KM = 25

st.set_page_config(
    page_title="Steel Plants & Exposure",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Load the notebook's exports. Cached so filtering never re-reads disk."""
    plants = pd.read_parquet(DATA_DIR / "plants_clean.parquet")
    litpop = pd.read_parquet(DATA_DIR / "plants_litpop.parquet")
    companies = pd.read_parquet(DATA_DIR / "companies.parquet")
    meta = (
        pd.read_csv(DATA_DIR / "metadata.csv").set_index("key")["value"].to_dict()
        if (DATA_DIR / "metadata.csv").exists()
        else {}
    )
    return plants, litpop, companies, meta


if not DATA_DIR.exists():
    st.error(
        f"Missing `{DATA_DIR}`.\n\n"
        "Run all cells of `lab_1.ipynb` first — Part 6 writes the files this app reads."
    )
    st.stop()

plants, litpop, companies, meta = load_data()

EXPOSURE_COL = f"litpop_sum_{NEIGHBOURHOOD_KM}km_usd"


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("🏭 Global Steel Plants & Socio-Economic Exposure")
st.markdown(
    "Plant locations and capacity from the **Global Energy Monitor – Global Iron and "
    "Steel Tracker**, combined with **LitPop** (ETH Zurich) asset-exposure grids to ask "
    "*what sits around each industrial asset?*"
)

# --------------------------------------------------------------------------
# Sidebar filters
# --------------------------------------------------------------------------
st.sidebar.header("Filters")

dataset_choice = st.sidebar.radio(
    "Dataset",
    ["Global (all plants)", f"LitPop subset ({meta.get('litpop_coverage', 'CHN/IND/JPN')})"],
    help=(
        "LitPop samples cover China, India and Japan only, so exposure views are "
        "limited to those countries."
    ),
)
is_global = dataset_choice.startswith("Global")
df = plants if is_global else litpop

regions = sorted(df["Region"].dropna().unique())
sel_regions = st.sidebar.multiselect("Region", regions, default=regions)
df = df[df["Region"].isin(sel_regions)]

countries = sorted(df["Country/area"].dropna().unique())
sel_countries = st.sidebar.multiselect(
    "Country / area", countries, default=countries,
    help="Narrowed by the regions selected above.",
)
df = df[df["Country/area"].isin(sel_countries)]

# Company selector: list the largest first so the useful ones are reachable.
owner_order = (
    df.groupby("Owner")["capacity_ttpa"].sum().sort_values(ascending=False).index.tolist()
)
sel_owners = st.sidebar.multiselect(
    "Company (owner)", owner_order, default=[],
    help="Leave empty to include every company.",
)
if sel_owners:
    df = df[df["Owner"].isin(sel_owners)]

# Capacity range.
cap = df["capacity_ttpa"].dropna()
if not cap.empty:
    cap_min, cap_max = float(cap.min()), float(cap.max())
    if cap_min < cap_max:
        lo, hi = st.sidebar.slider(
            "Operating capacity (ttpa)",
            min_value=cap_min, max_value=cap_max,
            value=(cap_min, cap_max), step=max((cap_max - cap_min) / 100, 1.0),
        )
        df = df[df["capacity_ttpa"].between(lo, hi) | df["capacity_ttpa"].isna()]

include_no_cap = st.sidebar.checkbox(
    "Include plants with no operating capacity", value=True,
    help="Plants whose units are announced, under construction, mothballed or retired.",
)
if not include_no_cap:
    df = df[df["capacity_ttpa"].notna()]

st.sidebar.markdown("---")
st.sidebar.caption(f"**{len(df):,}** plants match the current filters.")

if df.empty:
    st.warning("No plants match the current filters. Widen your selection in the sidebar.")
    st.stop()

# --------------------------------------------------------------------------
# KPIs
# --------------------------------------------------------------------------
total_cap = df["capacity_ttpa"].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plants", f"{len(df):,}")
c2.metric("Operating capacity", f"{total_cap / 1_000:,.1f} Mtpa")
c3.metric("Companies", f"{df['Owner'].nunique():,}")
c4.metric("Countries / areas", f"{df['Country/area'].nunique():,}")

if not is_global and EXPOSURE_COL in df.columns:
    e1, e2, e3 = st.columns(3)
    e1.metric(
        f"Median exposure within {NEIGHBOURHOOD_KM} km",
        f"${df[EXPOSURE_COL].median() / 1e9:,.1f} bn",
    )
    e2.metric("Total exposure in view", f"${df[EXPOSURE_COL].sum() / 1e12:,.2f} tn")
    e3.metric("Median match distance", f"{df['match_distance_km'].median():.1f} km")

st.markdown("---")

# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
tab_map, tab_explore, tab_company, tab_data = st.tabs(
    ["🗺️ Map", "📊 Exploration", "🏢 Companies", "📋 Data"]
)

with tab_map:
    mappable = df[df["Latitude"].notna() & df["Longitude"].notna()].copy()
    plottable = mappable[mappable["capacity_ttpa"].fillna(0) > 0]

    colour_options = ["Region", "Country/area", "Owner"]
    if not is_global and EXPOSURE_COL in df.columns:
        colour_options.insert(0, f"LitPop exposure within {NEIGHBOURHOOD_KM} km")

    colour_by = st.selectbox("Colour markers by", colour_options)

    if plottable.empty:
        st.info("No plants with operating capacity in the current selection to size markers by.")
    else:
        hover = {
            "Owner": True, "Country/area": True,
            "capacity_ttpa": ":,.0f", "Latitude": False, "Longitude": False,
        }
        if colour_by.startswith("LitPop"):
            # Log scale: a few megacity cells would otherwise saturate the palette.
            plot_df = plottable.copy()
            plot_df["log10_exposure"] = np.log10(
                plot_df[EXPOSURE_COL].where(plot_df[EXPOSURE_COL] > 0)
            )
            plot_df["exposure_busd"] = plot_df[EXPOSURE_COL] / 1e9
            hover["exposure_busd"] = ":,.1f"
            fig = px.scatter_map(
                plot_df, lat="Latitude", lon="Longitude",
                size="capacity_ttpa", color="log10_exposure",
                color_continuous_scale="Turbo", size_max=34, zoom=2.2,
                hover_name="Plant name (English)", hover_data=hover,
                map_style=MAP_STYLE,
                labels={"exposure_busd": f"Exposure {NEIGHBOURHOOD_KM} km (bn USD)",
                        "capacity_ttpa": "Capacity (ttpa)"},
            )
            fig.update_layout(coloraxis_colorbar_title="log10<br>USD")
        else:
            plot_df = plottable
            fig = px.scatter_map(
                plot_df, lat="Latitude", lon="Longitude",
                size="capacity_ttpa", color=colour_by,
                size_max=34, zoom=1.2,
                hover_name="Plant name (English)", hover_data=hover,
                map_style=MAP_STYLE,
                labels={"capacity_ttpa": "Capacity (ttpa)"},
            )
        fig.update_layout(height=640, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width='stretch')

    with st.expander("Plant density heatmap"):
        fig_d = px.density_map(
            mappable, lat="Latitude", lon="Longitude", radius=18,
            zoom=1.2, color_continuous_scale="Inferno", map_style=MAP_STYLE,
        )
        fig_d.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_d, width='stretch')

with tab_explore:
    left, right = st.columns(2)

    with left:
        st.subheader("Capacity by country / area")
        by_country = (
            df.groupby("Country/area")
            .agg(plants=("GEM plant ID", "size"), capacity=("capacity_ttpa", "sum"))
            .nlargest(15, "capacity").reset_index()
        )
        fig = px.bar(by_country, x="capacity", y="Country/area", orientation="h",
                     color="capacity", color_continuous_scale="Blues",
                     labels={"capacity": "Capacity (ttpa)", "Country/area": ""})
        fig.update_layout(yaxis={"categoryorder": "total ascending"},
                          coloraxis_showscale=False, height=460)
        st.plotly_chart(fig, width='stretch')

    with right:
        st.subheader("Plant age distribution")
        age_df = df[df["Plant age (years)"].notna()]
        if age_df.empty:
            st.info("No plant-age data in the current selection.")
        else:
            fig = px.histogram(age_df, x="Plant age (years)", nbins=40, color="Region")
            fig.update_layout(height=460, bargap=0.05, yaxis_title="Plants")
            st.plotly_chart(fig, width='stretch')

    st.subheader("Capacity distribution across plants")
    cap_df = df[df["capacity_ttpa"].fillna(0) > 0]
    if not cap_df.empty:
        fig = px.histogram(cap_df, x="capacity_ttpa", nbins=50,
                           labels={"capacity_ttpa": "Operating capacity (ttpa)"})
        fig.update_xaxes(type="log")
        fig.update_layout(height=380, bargap=0.05, yaxis_title="Plants")
        st.plotly_chart(fig, width='stretch')
        st.caption("Log x-axis: plant capacity is heavily right-skewed.")

    if not is_global and EXPOSURE_COL in df.columns:
        st.subheader("Capacity vs surrounding asset exposure")
        sc = df[(df["capacity_ttpa"].fillna(0) > 0) & (df[EXPOSURE_COL] > 0)]
        if not sc.empty:
            fig = px.scatter(
                sc, x=EXPOSURE_COL, y="capacity_ttpa", color="Country/area",
                hover_name="Plant name (English)", log_x=True, log_y=True,
                labels={EXPOSURE_COL: f"LitPop exposure within {NEIGHBOURHOOD_KM} km (USD)",
                        "capacity_ttpa": "Operating capacity (ttpa)"},
            )
            fig.update_layout(height=460)
            st.plotly_chart(fig, width='stretch')

with tab_company:
    st.subheader("Company-level footprint")
    st.caption(
        "Aggregated over the LitPop-covered subset "
        f"({meta.get('litpop_coverage', 'China, India, Japan')}), as computed in Part 5."
    )
    visible_owners = set(df["Owner"].unique())
    comp = companies[companies["Owner"].isin(visible_owners)]

    if comp.empty:
        st.info("No company aggregates for the current selection. Try the LitPop subset.")
    else:
        top_n = st.slider("Companies to show", 10, min(100, len(comp)),
                          min(40, len(comp)), step=5)
        top = comp.nlargest(top_n, "total_capacity_ttpa")

        fig = px.scatter(
            top, x="mean_local_exposure_usd", y="total_capacity_ttpa",
            size="n_plants", color="n_plants", hover_name="Owner",
            log_x=True, log_y=True, size_max=32, color_continuous_scale="Viridis",
            labels={"mean_local_exposure_usd": "Mean local exposure (USD)",
                    "total_capacity_ttpa": "Total capacity (ttpa)",
                    "n_plants": "Plants"},
        )
        fig.update_layout(height=480)
        st.plotly_chart(fig, width='stretch')

        st.dataframe(
            top[["Owner", "n_plants", "total_capacity_ttpa", "n_countries",
                 "mean_plant_age", "mean_local_exposure_usd",
                 "capacity_weighted_exposure_usd", "countries"]],
            width='stretch', hide_index=True,
        )

with tab_data:
    st.subheader("Filtered plant data")
    st.dataframe(df, width='stretch', hide_index=True)
    st.download_button(
        "⬇️ Download filtered data (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        file_name="steel_plants_filtered.csv",
        mime="text/csv",
    )

# --------------------------------------------------------------------------
# Footer
# --------------------------------------------------------------------------
st.markdown("---")
st.caption(
    f"""
**Sources** — Plants: Global Energy Monitor, *Global Iron and Steel Tracker*
({meta.get('source_plants', 'June 2026 V1')}).
Exposure: **LitPop** (ETH Zurich), {meta.get('litpop_resolution', '300 arcsec')},
financial mode {meta.get('litpop_fin_mode', 'pc')}, reference year
{meta.get('litpop_ref_year', '2018')}, values in {meta.get('litpop_value_unit', 'USD')}.

**Notes** — "Capacity" is the sum of *operating* crude-steel units per plant
({meta.get('capacity_definition', '')}). LitPop covers
{meta.get('litpop_coverage', 'China, India, Japan')} only, so exposure figures apply to
those countries. LitPop `value` is **produced capital**, an asset-value proxy — not a
population count. Exposure is matched by nearest grid cell (haversine BallTree) and
summed within {NEIGHBOURHOOD_KM} km.

AIDAMS Lab 1 — Ben Njima, Gueddas, Mallat, Sanver, Tanaci.
"""
)
