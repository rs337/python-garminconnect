#!/usr/bin/env python3
"""Manually correct Garmin's auto-detected workout sets.

Garmin often misreads which exercise you did, or how many reps/how much
weight, for strength-training activities. This app loads the "sets" table
that `fetch_latest_workout.py` saved into `workouts.db`, lets you edit
exercise_name / reps / weight_kg inline, and writes your corrections back to
the database.

Run with:
    streamlit run review_workouts.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent / "workouts.db"
TABLE_NAME = "sets"
# Columns you're actually allowed to correct — everything else is read-only.
EDITABLE_COLUMNS = ["exercise_name", "reps", "weight_kg"]

st.set_page_config(page_title="Review Workouts", page_icon="🏋️")
st.title("🏋️ Review & Correct Workout Sets")
st.caption("Fix anything Garmin auto-detected wrong, then save your changes.")


def load_sets() -> pd.DataFrame:
    """Read the whole "sets" table from workouts.db into a DataFrame."""
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn)


def save_sets(df: pd.DataFrame) -> None:
    """Overwrite the "sets" table in workouts.db with the edited DataFrame."""
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)


if not DB_PATH.exists():
    st.error(f"No {DB_PATH.name} found. Run fetch_latest_workout.py first.")
    st.stop()

original_df = load_sets()
if original_df.empty:
    st.info("The sets table is empty. Run fetch_latest_workout.py to add a workout.")
    st.stop()

# st.data_editor gives back an edited copy of the DataFrame; row order/count
# stays the same because we disable adding/deleting rows below.
edited_df = st.data_editor(
    original_df,
    hide_index=True,
    num_rows="fixed",
    disabled=[col for col in original_df.columns if col not in EDITABLE_COLUMNS],
    column_config={
        "manually_corrected": st.column_config.CheckboxColumn("Manually corrected"),
    },
)

if st.button("💾 Save changes"):
    # A row counts as "manually corrected" if any editable cell differs from
    # what was loaded from the database. `.ne()` treats matching NaNs as
    # unequal by default, so we also allow "both sides are NaN" as no-change.
    changed = pd.Series(False, index=edited_df.index)
    for col in EDITABLE_COLUMNS:
        cell_changed = edited_df[col].ne(original_df[col]) & ~(
            edited_df[col].isna() & original_df[col].isna()
        )
        changed |= cell_changed

    # Once a row has been corrected it stays flagged, even if you only edit
    # it again later — manually_corrected only ever turns True, never back off.
    edited_df["manually_corrected"] = original_df["manually_corrected"].astype(bool) | changed

    save_sets(edited_df)
    st.success(f"Saved {len(edited_df)} rows to {DB_PATH.name} ({changed.sum()} newly corrected).")
