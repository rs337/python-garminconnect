"""Pure formatting helpers.

These functions take raw values from the Garmin API (meters, meters/second,
seconds, milliseconds) and turn them into the units runners actually think
in (kilometers, min/km pace, mm:ss). Keeping this separate from the
Streamlit code means we can test and reuse it without needing a live
Garmin connection.
"""

from __future__ import annotations


def meters_to_km(meters: float | None) -> float:
    """Convert meters to kilometers, rounded to 2 decimal places."""
    if not meters:
        return 0.0
    return round(meters / 1000, 2)


def seconds_to_clock(seconds: float | None) -> str:
    """Format a duration in seconds as ``H:MM:SS`` or ``MM:SS``."""
    if not seconds or seconds < 0:
        return "0:00"

    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def speed_to_pace(speed_mps: float | None) -> str:
    """Convert a speed in meters/second to a running pace string, e.g. ``5:06 /km``.

    Garmin reports speed rather than pace, but pace (minutes per km) is the
    unit most runners think in.
    """
    if not speed_mps or speed_mps <= 0:
        return "--:--"

    seconds_per_km = 1000 / speed_mps
    minutes, seconds = divmod(int(round(seconds_per_km)), 60)
    return f"{minutes}:{seconds:02d} /km"


def round_or_dash(value: float | None, decimals: int = 1) -> str:
    """Round a numeric value for display, or show a dash when it's missing.

    Garmin doesn't always report running-dynamics metrics (e.g. a lap that's
    mostly standing still may have no ground contact time), so this avoids
    printing ``None`` in the dashboard.
    """
    if value is None:
        return "--"
    return f"{round(value, decimals)}"
