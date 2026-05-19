from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import date, datetime, timedelta
from urllib.request import Request, urlopen


BASE_URL = "https://www.caiso.com/outlook/history/{yyyymmdd}/demand.csv"


def download_range(start: date, end: date, output: str, sleep_seconds: float = 0.2) -> dict:
    rows: list[dict] = []
    current = start
    while current <= end:
        rows.extend(download_day(current))
        if sleep_seconds:
            time.sleep(sleep_seconds)
        current += timedelta(days=1)

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "date",
                "time",
                "day_ahead_forecast_mw",
                "hour_ahead_forecast_mw",
                "current_demand_mw",
                "demand_response_mw",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return {
        "source": "CAISO Today's Outlook demand history",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "rows": len(rows),
        "output": output,
        "url_pattern": BASE_URL,
    }


def download_day(day: date) -> list[dict]:
    yyyymmdd = day.strftime("%Y%m%d")
    url = BASE_URL.format(yyyymmdd=yyyymmdd)
    request = Request(url, headers={"User-Agent": "AEI-V2G research downloader"})
    with urlopen(request, timeout=30) as response:
        content = response.read().decode("utf-8-sig")

    rows: list[dict] = []
    reader = csv.DictReader(content.splitlines())
    for raw in reader:
        time_value = raw.get("Time", "").strip()
        if not time_value:
            continue
        if time_value == "00:00" and rows:
            # CAISO chart exports repeat the next-day boundary at the end of each
            # historical day. Keep the opening 00:00 row and skip the duplicate.
            continue
        timestamp = datetime.combine(day, datetime.strptime(time_value, "%H:%M").time()).isoformat()
        rows.append(
            {
                "timestamp": timestamp,
                "date": day.isoformat(),
                "time": time_value,
                "day_ahead_forecast_mw": number(raw.get("Day ahead forecast")),
                "hour_ahead_forecast_mw": number(raw.get("Hour ahead forecast")),
                "current_demand_mw": number(raw.get("Current demand")),
                "demand_response_mw": number(raw.get("Demand response")),
                "source": "CAISO",
            }
        )
    return rows


def number(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return ""
    return str(float(cleaned))


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    parser.add_argument("--output", required=True)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    args = parser.parse_args()
    result = download_range(parse_date(args.start), parse_date(args.end), args.output, args.sleep_seconds)
    print(result)


if __name__ == "__main__":
    main()
