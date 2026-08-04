"""
Capture step: download today's transient orders.csv, preserve it raw, and log
the attempt. This step needs NO database, so it runs unattended in GitHub
Actions and guarantees the fragile daily file is never lost.

Usage:
    uv run python -m src.capture                 # capture "today" (UTC)
    uv run python -m src.capture 2026-08-03      # capture a specific date
"""

import sys
import uuid

import requests

from helpers import config, io, logs


def classify_file(path, expected_date):
    """Inspect a saved raw file and decide its status without any network.

    Returns (status, rows_loaded, source_date_found). Kept separate from the
    download so the logic is easy to test on local files.
    """
    df = io.read_orders_csv(path)
    rows = len(df)
    if rows == 0:
        return config.STATUS_EMPTY, 0, ""
    found = df["order_date"].dropna().unique().tolist()
    found_date = found[0] if len(found) == 1 else ";".join(map(str, found))
    if expected_date and found_date != expected_date:
        return config.STATUS_STALE, rows, found_date
    return config.STATUS_SUCCESS, rows, found_date


def capture(expected_date=None):
    expected_date = expected_date or io.utc_now_iso()[:10]
    out_path = config.RAW_DIR / f"orders_{expected_date}.csv"
    log_row = {
        "run_id": uuid.uuid4().hex,
        "run_timestamp": io.utc_now_iso(),
        "source_url": config.ORDERS_URL,
        "source_date_expected": expected_date,
        "source_date_found": "",
        "status": config.STATUS_FAILED,
        "rows_loaded": 0,
        "file_hash": "",
        "error_message": "",
    }

    try:
        resp = requests.get(config.ORDERS_URL, timeout=60)
        resp.raise_for_status()
        config.RAW_DIR.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)

        status, rows, found_date = classify_file(out_path, expected_date)
        log_row.update({
            "status": status,
            "rows_loaded": rows,
            "source_date_found": found_date,
            "file_hash": io.file_hash(out_path),
        })
        print(f"[capture] {out_path.name}: status={status} rows={rows}")
    except Exception as exc:  # noqa: BLE001 - log any failure honestly
        log_row["status"] = config.STATUS_FAILED
        log_row["error_message"] = str(exc)
        print(f"[capture] FAILED: {exc}")

    logs.append_ingestion_log(log_row)
    return log_row


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    capture(arg)
