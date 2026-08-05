"""
End-to-end pipeline orchestrator: runs every step in the correct order against
the local SQLite database. This is the single command to (re)build everything.

It only calls the existing step functions -- no business logic lives here -- so
it never duplicates or changes what the individual scripts do.

Order (dependencies matter):
    init_db -> reference -> load_raw -> check_quality -> crosswalk
            -> clean_orders -> weather -> daily_sales

Usage:
    uv run python -m src.run_pipeline              # rebuild from existing data/raw
    uv run python -m src.run_pipeline --capture    # also download today's file first
    uv run python -m src.run_pipeline --no-weather # skip the network weather step
"""

import sys

from src import (capture, check_quality, crosswalk, init_db, load_raw,
                 reference, transform, weather)


def main(do_capture=False, do_weather=True):
    if do_capture:
        capture.capture()                        # download today's orders (network)

    init_db.init_db()                            # ensure schema exists
    reference.load_reference_into_sqlite()       # stores/products/new_products -> SQLite
    load_raw.load_raw()                          # data/raw -> raw_orders (+ ingestion_log)
    check_quality.check_quality()                # -> data_quality_log.csv
    crosswalk.build_crosswalk()                  # products <-> new_products
    transform.build_clean_orders()               # raw_orders -> clean_orders
    if do_weather:
        try:
            weather.fetch_weather()              # Open-Meteo -> weather_daily (network)
        except Exception as exc:  # noqa: BLE001 - never let weather block the build
            print(f"[pipeline] weather step skipped ({exc})")
    transform.build_daily_sales()                # clean_orders (+weather) -> daily_sales
    print("[pipeline] done")


if __name__ == "__main__":
    main(do_capture="--capture" in sys.argv,
         do_weather="--no-weather" not in sys.argv)
