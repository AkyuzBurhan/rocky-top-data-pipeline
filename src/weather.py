"""
Weather enrichment via Open-Meteo (free, no API key).

Grain: one row per store per date -> weather_daily. Raw API responses are cached
under data/weather_cache/ so we do not re-hit the API and can prove provenance.

Uses each store's latitude/longitude (from the stores reference) and the date
range found in clean_orders. Requires network, so run it on your machine (not in
GitHub Actions, which uses the cached JSON if committed).

Note: the Open-Meteo archive (ERA5) lags reality by a few days, so the most
recent 1-2 order dates may have no weather row yet; those simply join as NULL in
daily_sales. Re-run later to fill them.

Usage:
    uv run python -m src.weather
"""

import json

import pandas as pd
import requests

from helpers import config, db

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_SOURCE = "open-meteo-archive"
DAILY_VARS = "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"


def _cache_path(store_id, start, end):
    return config.WEATHER_CACHE_DIR / f"{store_id}_{start}_{end}.json"


def _purge_stale_cache(store_id, keep):
    """Remove older cache files for this store (from a different date range) so
    the folder keeps exactly one file per store as the range grows."""
    if not config.WEATHER_CACHE_DIR.exists():
        return
    for old in config.WEATHER_CACHE_DIR.glob(f"{store_id}_*.json"):
        if old != keep:
            old.unlink()


def _fetch_store(store_id, lat, lon, start, end):
    """Return Open-Meteo JSON for one store/date-range, using the cache if present."""
    cache = _cache_path(store_id, start, end)
    _purge_stale_cache(store_id, cache)      # keep only the current range per store
    if cache.exists():
        return json.loads(cache.read_text())
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": DAILY_VARS, "timezone": "America/New_York",
    }
    resp = requests.get(ARCHIVE_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    config.WEATHER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    return data


def fetch_weather(engine=None):
    engine = engine or db.get_sqlite_engine()
    try:
        stores = pd.read_sql(
            "SELECT store_id, latitude, longitude FROM stores", engine)
        dates = pd.read_sql("SELECT DISTINCT order_date FROM clean_orders", engine)
    except Exception:
        print("[weather] stores/clean_orders not ready; skipping")
        return 0
    if stores.empty or dates.empty:
        print("[weather] no stores or dates; skipping")
        return 0

    d = sorted(x for x in dates["order_date"].dropna().tolist() if x)
    start, end = d[0], d[-1]

    rows = []
    for _, s in stores.iterrows():
        data = _fetch_store(s["store_id"], s["latitude"], s["longitude"], start, end)
        daily = data.get("daily", {})
        times = daily.get("time", [])
        for i, day in enumerate(times):
            rows.append({
                "weather_date": day,
                "store_id": s["store_id"],
                "temperature_2m_max": daily["temperature_2m_max"][i],
                "temperature_2m_min": daily["temperature_2m_min"][i],
                "precipitation_sum": daily["precipitation_sum"][i],
                "weather_code": daily["weather_code"][i],
                "weather_source": WEATHER_SOURCE,
            })

    wdf = pd.DataFrame(rows)
    wdf.to_sql("weather_daily", engine, if_exists="replace", index=False)
    print(f"[weather] weather_daily rebuilt: {len(wdf)} rows "
          f"({stores.shape[0]} stores x {len(d)} dates, {start}..{end})")
    return len(wdf)


if __name__ == "__main__":
    fetch_weather()
