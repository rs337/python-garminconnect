"""Local Garmin Connect running dashboard.

This package is intentionally small and split into three simple pieces:

- ``garmin_data.py``  — talks to Garmin Connect and returns plain dicts/lists.
- ``formatting.py``   — pure functions that turn raw numbers (m/s, ms, meters)
  into human-readable text (min/km, mm:ss, km).
- ``app.py``          — the Streamlit page itself, which just calls the two
  modules above and renders the results.
"""
