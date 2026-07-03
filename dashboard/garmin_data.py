"""Functions for talking to Garmin Connect.

Every function here takes a logged-in `Garmin` client and returns plain
Python dicts/lists — there's no Streamlit code in this file. That keeps the
"talk to Garmin" logic separate from the "draw the web page" logic in
`app.py`, and means these functions could just as easily be reused from a
notebook or a test.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

DEFAULT_TOKEN_STORE = Path(os.getenv("GARMINTOKENS", "~/.garminconnect")).expanduser()


class GarminLoginError(RuntimeError):
    """Raised when we can't log in to Garmin Connect with what's available."""


def login(token_store: Path = DEFAULT_TOKEN_STORE) -> Garmin:
    """Log in to Garmin Connect, reusing a cached session token when possible.

    Falls back to the ``EMAIL`` / ``PASSWORD`` environment variables (loaded
    from `.env` by `app.py`) if there's no valid cached token yet.
    """
    client = Garmin()
    try:
        client.login(str(token_store))
        return client
    except GarminConnectTooManyRequestsError as err:
        raise GarminLoginError(f"Garmin is rate-limiting login attempts: {err}") from err
    except (GarminConnectAuthenticationError, GarminConnectConnectionError):
        pass  # No valid cached token yet — fall through to a fresh login below.

    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    if not email or not password:
        raise GarminLoginError(
            "No cached Garmin session found, and EMAIL/PASSWORD are not set in .env."
        )

    client = Garmin(email=email, password=password)
    client.login(str(token_store))
    return client


def get_activities_for_date(client: Garmin, day: date) -> list[dict[str, Any]]:
    """Return every activity recorded on `day`, newest first."""
    iso_day = day.isoformat()
    activities = client.get_activities_by_date(iso_day, iso_day)
    return activities or []


def get_activity_summary(client: Garmin, activity_id: int | str) -> dict[str, Any]:
    """Return the full summary for one activity (overall averages, metadata, etc.)."""
    return client.get_activity(activity_id)


def get_activity_laps(client: Garmin, activity_id: int | str) -> list[dict[str, Any]]:
    """Return one row per lap for an activity.

    Each lap includes an ``intensityType`` for structured workouts —
    ``WARMUP`` / ``ACTIVE`` / ``RECOVERY`` / ``COOLDOWN`` — which is how we
    group laps into "the interval section" on the dashboard.
    """
    splits = client.get_activity_splits(activity_id)
    if isinstance(splits, dict):
        return splits.get("lapDTOs", []) or []
    return []
