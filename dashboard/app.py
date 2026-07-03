"""Local Garmin Connect running dashboard.

Run this with:

    streamlit run dashboard/app.py

It logs in to Garmin Connect (reusing the same cached token as
`example.py` / the exploration notebook), lets you pick a run, and shows:

- A summary card with the whole-run averages (distance, pace, cadence,
  ground contact time, vertical oscillation, ...).
- A per-interval table, so you can see how each warmup/interval/recovery/
  cooldown segment went.

See `notebooks/explore_activity_data.ipynb` for how we figured out which
Garmin fields to use here.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# `streamlit run dashboard/app.py` only puts this file's own directory on
# sys.path, not the repo root — add it so `from dashboard import ...` and
# `from garminconnect import ...` work no matter where streamlit is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard import garmin_data
from dashboard.formatting import (
    meters_to_km,
    round_or_dash,
    seconds_to_clock,
    speed_to_pace,
)
from garminconnect import Garmin

load_dotenv()

st.set_page_config(page_title="Run Dashboard", page_icon="🏃", layout="wide")


@st.cache_resource(show_spinner="Connecting to Garmin Connect...")
def get_client() -> Garmin:
    return garmin_data.login()


@st.cache_data(ttl=300, show_spinner="Fetching activities...")
def load_activities_for_date(_client: Garmin, day: date) -> list[dict]:
    return garmin_data.get_activities_for_date(_client, day)


@st.cache_data(ttl=300, show_spinner="Loading activity summary...")
def load_activity_summary(_client: Garmin, activity_id: int) -> dict:
    return garmin_data.get_activity_summary(_client, activity_id)


@st.cache_data(ttl=300, show_spinner="Loading lap data...")
def load_activity_laps(_client: Garmin, activity_id: int) -> list[dict]:
    return garmin_data.get_activity_laps(_client, activity_id)


st.title("🏃 Run Dashboard")
st.caption("A local dashboard for exploring your Garmin Connect running activities.")

try:
    client = get_client()
except garmin_data.GarminLoginError as err:
    st.error(f"Couldn't log in to Garmin Connect: {err}")
    st.stop()

# --- Sidebar: pick which activity to look at --------------------------------
st.sidebar.header("Choose a run")
selected_date = st.sidebar.date_input("Date", value=date.today(), max_value=date.today())

if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

activities = load_activities_for_date(client, selected_date)

if not activities:
    st.info(
        f"No activities found on {selected_date.isoformat()}. "
        "Try a different date in the sidebar, or make sure the activity has "
        "synced to Garmin Connect."
    )
    st.stop()

activity_labels = {
    activity["activityId"]: f"{activity['activityName']} — {activity['startTimeLocal']}"
    for activity in activities
}
selected_id = st.sidebar.selectbox(
    "Activity",
    options=list(activity_labels.keys()),
    format_func=lambda activity_id: activity_labels[activity_id],
)

# --- Load the selected activity's data --------------------------------------
summary = load_activity_summary(client, selected_id)
laps = load_activity_laps(client, selected_id)
summary_stats = summary.get("summaryDTO", {})

# --- Header ------------------------------------------------------------------
st.header(summary.get("activityName", "Run"))
st.caption(summary.get("activityTypeDTO", {}).get("typeKey", "activity").title())

# --- Overall summary metrics --------------------------------------------------
row1 = st.columns(4)
row1[0].metric("Distance", f"{meters_to_km(summary_stats.get('distance')):.2f} km")
row1[1].metric("Duration", seconds_to_clock(summary_stats.get("duration")))
row1[2].metric("Avg Pace", speed_to_pace(summary_stats.get("averageSpeed")))
row1[3].metric("Avg HR", f"{round_or_dash(summary_stats.get('averageHR'), 0)} bpm")

row2 = st.columns(4)
row2[0].metric("Cadence", f"{round_or_dash(summary_stats.get('averageRunCadence'), 0)} spm")
row2[1].metric("Ground Contact", f"{round_or_dash(summary_stats.get('groundContactTime'), 0)} ms")
row2[2].metric("Vertical Osc.", f"{round_or_dash(summary_stats.get('verticalOscillation'))} cm")
row2[3].metric("Stride Length", f"{round_or_dash(summary_stats.get('strideLength'), 0)} cm")

st.divider()

# --- Per-interval breakdown ----------------------------------------------------
st.subheader("Interval breakdown")

if not laps:
    st.info("No lap data available for this activity.")
else:
    lap_rows = [
        {
            "Lap": lap.get("lapIndex"),
            "Type": str(lap.get("intensityType", "—")).title(),
            "Distance (km)": meters_to_km(lap.get("distance")),
            "Duration": seconds_to_clock(lap.get("duration")),
            "Pace": speed_to_pace(lap.get("averageSpeed")),
            "Avg Speed (m/s)": lap.get("averageSpeed") or 0.0,
            "Cadence (spm)": round_or_dash(lap.get("averageRunCadence"), 0),
            "Avg HR": round_or_dash(lap.get("averageHR"), 0),
            "GCT (ms)": round_or_dash(lap.get("groundContactTime"), 0),
            "Vert. Osc. (cm)": round_or_dash(lap.get("verticalOscillation")),
        }
        for lap in laps
    ]
    laps_df = pd.DataFrame(lap_rows)

    st.dataframe(
        laps_df.drop(columns=["Avg Speed (m/s)"]),
        hide_index=True,
        width="stretch",
    )

    st.caption("Speed per lap (taller bar = faster)")
    st.bar_chart(laps_df.set_index("Lap")["Avg Speed (m/s)"])
