#!/usr/bin/env python3
"""Fetch your most recent strength-training workout from Garmin Connect.

Logs in with the EMAIL/PASSWORD from `.env`, finds the newest strength
activity, turns Garmin's auto-detected exercise sets into a tidy pandas
DataFrame, prints it, and saves it into a local SQLite database
(`workouts.db`) so `review_workouts.py` can be used to fix anything Garmin
got wrong.

Run with:
    python fetch_latest_workout.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# Read EMAIL / PASSWORD from .env into the environment. Never hardcode
# credentials here, and never commit a .env file (it's in .gitignore).
load_dotenv()

DB_PATH = Path(__file__).resolve().parent / "workouts.db"
TABLE_NAME = "sets"
# How many of the most recent activities to look through for a strength one.
ACTIVITY_SCAN_LIMIT = 50


def login() -> Garmin:
    """Log in to Garmin Connect using the credentials from .env."""
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    if not email or not password:
        sys.exit("EMAIL and PASSWORD must be set in a .env file.")

    # prompt_mfa lets login() ask for a one-time code if your account has
    # multi-factor authentication turned on — it's only used if needed.
    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: input("MFA code: ").strip(),
    )
    try:
        client.login()
    except GarminConnectAuthenticationError:
        sys.exit("Login failed — check EMAIL/PASSWORD in .env.")
    except GarminConnectTooManyRequestsError as err:
        sys.exit(f"Garmin is rate-limiting login attempts: {err}")
    except GarminConnectConnectionError as err:
        sys.exit(f"Could not connect to Garmin Connect: {err}")
    return client


def find_latest_strength_activity(client: Garmin) -> dict[str, Any]:
    """Scan recent activities and return the newest strength-training one."""
    activities = client.get_activities(0, ACTIVITY_SCAN_LIMIT)
    for activity in activities:
        type_key = activity.get("activityType", {}).get("typeKey", "")
        if "strength" in type_key.lower():
            return activity
    sys.exit(
        f"No strength-training activity found in your last {ACTIVITY_SCAN_LIMIT} activities."
    )


def build_sets_dataframe(client: Garmin, activity: dict[str, Any]) -> pd.DataFrame:
    """Turn one activity's exercise sets into a DataFrame, one row per set."""
    activity_id = activity["activityId"]
    # Record the workout's own date, not each individual set's timestamp.
    date_recorded = activity["startTimeLocal"].split(" ")[0]

    exercise_data = client.get_activity_exercise_sets(activity_id)
    exercise_sets = exercise_data.get("exerciseSets", []) if exercise_data else []

    rows = []
    set_numbers: dict[str, int] = {}  # running set count per exercise name
    for exercise_set in exercise_sets:
        # Garmin logs a "REST" entry between working sets — those aren't sets
        # we want to track, so skip anything that isn't an active set.
        if exercise_set.get("setType") != "ACTIVE":
            continue

        exercises = exercise_set.get("exercises") or []
        if exercises:
            exercise_name = exercises[0].get("name") or exercises[0].get("category") or "UNKNOWN"
        else:
            exercise_name = "UNKNOWN"

        set_numbers[exercise_name] = set_numbers.get(exercise_name, 0) + 1

        # Garmin reports weight in grams; convert to kg for readability.
        weight_grams = exercise_set.get("weight")
        weight_kg = weight_grams / 1000 if weight_grams is not None else None

        rows.append(
            {
                "activity_id": activity_id,
                "exercise_name": exercise_name,
                "set_number": set_numbers[exercise_name],
                "reps": exercise_set.get("repetitionCount"),
                "weight_kg": weight_kg,
                "source": "garmin_auto",
                "date_recorded": date_recorded,
            }
        )

    columns = [
        "activity_id",
        "exercise_name",
        "set_number",
        "reps",
        "weight_kg",
        "source",
        "date_recorded",
    ]
    return pd.DataFrame(rows, columns=columns)


def save_to_sqlite(df: pd.DataFrame, activity_id: int) -> None:
    """Insert the DataFrame's rows into workouts.db, unless this activity is already stored."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                activity_id INTEGER,
                exercise_name TEXT,
                set_number INTEGER,
                reps INTEGER,
                weight_kg REAL,
                source TEXT,
                date_recorded TEXT,
                manually_corrected INTEGER DEFAULT 0
            )
            """
        )

        already_stored = conn.execute(
            f"SELECT 1 FROM {TABLE_NAME} WHERE activity_id = ? LIMIT 1",
            (activity_id,),
        ).fetchone()
        if already_stored:
            print(f"\nActivity {activity_id} is already in {DB_PATH.name} — skipping insert.")
            return

        # manually_corrected starts False; review_workouts.py flips it to True
        # for any row you edit by hand.
        to_insert = df.copy()
        to_insert["manually_corrected"] = 0
        to_insert.to_sql(TABLE_NAME, conn, if_exists="append", index=False)
        print(f"\nSaved {len(to_insert)} sets for activity {activity_id} to {DB_PATH.name}.")


def main() -> None:
    client = login()
    activity = find_latest_strength_activity(client)
    df = build_sets_dataframe(client, activity)

    if df.empty:
        sys.exit(f"Activity {activity['activityId']} has no exercise sets to record.")

    print(
        f"\nLatest strength activity: {activity.get('activityName')} "
        f"({activity['startTimeLocal']})\n"
    )
    print(df.to_string(index=False))

    save_to_sqlite(df, activity["activityId"])


if __name__ == "__main__":
    main()
