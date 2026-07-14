import argparse
import csv
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GOLD_ROOT = PROJECT_ROOT / "data" / "gold" / "bus_arrival_kpis"
FINAL_REPORT_ROOT = PROJECT_ROOT / "data" / "final_reports"

SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


def safe_int(value):
    try:
        if value in ("", None):
            return 0
        return int(float(value))
    except ValueError:
        return 0


def safe_float(value):
    try:
        if value in ("", None):
            return None
        return float(value)
    except ValueError:
        return None


def parse_sgt_timestamp(value: str):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SINGAPORE_TZ)

    return dt.astimezone(SINGAPORE_TZ)


def read_all_gold_rows():
    gold_files = sorted(GOLD_ROOT.rglob("*.csv"))

    rows = []

    for gold_file in gold_files:
        with gold_file.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                row["_source_gold_file"] = str(gold_file)
                rows.append(row)

    return rows


def filter_rows_by_sgt_window(rows, report_date: str, start_time: str, end_time: str):
    report_date_obj = datetime.strptime(report_date, "%Y-%m-%d").date()
    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
    end_time_obj = datetime.strptime(end_time, "%H:%M").time()

    filtered = []

    for row in rows:
        ts = parse_sgt_timestamp(row.get("kpi_created_timestamp_sgt", ""))

        if ts is None:
            continue

        if ts.date() != report_date_obj:
            continue

        if not (start_time_obj <= ts.time().replace(second=0, microsecond=0) <= end_time_obj):
            continue

        row["_parsed_sgt_timestamp"] = ts
        filtered.append(row)

    return filtered


def weighted_average(total_weighted_value, total_weight):
    if total_weight == 0:
        return None
    return round(total_weighted_value / total_weight, 2)


def aggregate_hourly(rows):
    groups = defaultdict(list)

    for row in rows:
        ts = row["_parsed_sgt_timestamp"]

        key = (
            ts.date().isoformat(),
            ts.strftime("%A"),
            row.get("day_type", ""),
            row.get("bus_stop_code", ""),
            row.get("service_no", ""),
            row.get("operator", ""),
            ts.hour,
        )

        groups[key].append(row)

    output = []

    for (
        report_date,
        day_name,
        day_type,
        bus_stop_code,
        service_no,
        operator,
        report_hour,
    ), group_rows in groups.items():

        total_arrival_records = 0
        weighted_wait_sum = 0.0
        weighted_wait_count = 0

        min_wait_values = []
        max_wait_values = []

        totals = {
            "monitored_bus_count": 0,
            "unmonitored_bus_count": 0,
            "seat_available_count": 0,
            "standing_available_count": 0,
            "limited_standing_count": 0,
            "unknown_load_count": 0,
            "single_deck_count": 0,
            "double_deck_count": 0,
            "bendy_bus_count": 0,
            "unknown_bus_type_count": 0,
            "wheelchair_accessible_count": 0,
        }

        for row in group_rows:
            arrival_count = safe_int(row.get("arrival_record_count"))
            total_arrival_records += arrival_count

            avg_wait = safe_float(row.get("avg_wait_time_minutes"))
            min_wait = safe_float(row.get("min_wait_time_minutes"))
            max_wait = safe_float(row.get("max_wait_time_minutes"))

            if avg_wait is not None and arrival_count > 0:
                weighted_wait_sum += avg_wait * arrival_count
                weighted_wait_count += arrival_count

            if min_wait is not None:
                min_wait_values.append(min_wait)

            if max_wait is not None:
                max_wait_values.append(max_wait)

            for col in totals:
                totals[col] += safe_int(row.get(col))

        api_pull_count = len(group_rows)

        output.append(
            {
                "report_date": report_date,
                "day_name": day_name,
                "day_type": day_type,
                "bus_stop_code": bus_stop_code,
                "service_no": service_no,
                "operator": operator,
                "report_hour": report_hour,
                "api_pull_count": api_pull_count,
                "arrival_record_count": total_arrival_records,
                "avg_wait_time_minutes": weighted_average(weighted_wait_sum, weighted_wait_count),
                "min_wait_time_minutes": round(min(min_wait_values), 2) if min_wait_values else None,
                "max_wait_time_minutes": round(max(max_wait_values), 2) if max_wait_values else None,
                **totals,
            }
        )

    return sorted(output, key=lambda x: (x["report_hour"], x["service_no"]))


def aggregate_daily(hourly_rows):
    groups = defaultdict(list)

    for row in hourly_rows:
        key = (
            row["report_date"],
            row["day_name"],
            row["day_type"],
            row["bus_stop_code"],
            row["service_no"],
            row["operator"],
        )
        groups[key].append(row)

    output = []

    for (
        report_date,
        day_name,
        day_type,
        bus_stop_code,
        service_no,
        operator,
    ), group_rows in groups.items():

        total_arrival_records = 0
        weighted_wait_sum = 0.0
        weighted_wait_count = 0

        min_wait_values = []
        max_wait_values = []

        totals = {
            "monitored_bus_count": 0,
            "unmonitored_bus_count": 0,
            "seat_available_count": 0,
            "standing_available_count": 0,
            "limited_standing_count": 0,
            "unknown_load_count": 0,
            "single_deck_count": 0,
            "double_deck_count": 0,
            "bendy_bus_count": 0,
            "unknown_bus_type_count": 0,
            "wheelchair_accessible_count": 0,
        }

        api_pull_count = 0

        for row in group_rows:
            arrival_count = safe_int(row.get("arrival_record_count"))
            total_arrival_records += arrival_count
            api_pull_count += safe_int(row.get("api_pull_count"))

            avg_wait = safe_float(row.get("avg_wait_time_minutes"))
            min_wait = safe_float(row.get("min_wait_time_minutes"))
            max_wait = safe_float(row.get("max_wait_time_minutes"))

            if avg_wait is not None and arrival_count > 0:
                weighted_wait_sum += avg_wait * arrival_count
                weighted_wait_count += arrival_count

            if min_wait is not None:
                min_wait_values.append(min_wait)

            if max_wait is not None:
                max_wait_values.append(max_wait)

            for col in totals:
                totals[col] += safe_int(row.get(col))

        output.append(
            {
                "report_date": report_date,
                "day_name": day_name,
                "day_type": day_type,
                "bus_stop_code": bus_stop_code,
                "service_no": service_no,
                "operator": operator,
                "api_pull_count": api_pull_count,
                "arrival_record_count": total_arrival_records,
                "avg_wait_time_minutes": weighted_average(weighted_wait_sum, weighted_wait_count),
                "min_wait_time_minutes": round(min(min_wait_values), 2) if min_wait_values else None,
                "max_wait_time_minutes": round(max(max_wait_values), 2) if max_wait_values else None,
                **totals,
            }
        )

    return sorted(output, key=lambda x: x["service_no"])


def write_csv(records, output_file: Path):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not records:
        output_file.write_text("", encoding="utf-8")
        return

    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Singapore report date, e.g. 2026-07-10")
    parser.add_argument("--start", default="05:00", help="Start time in Singapore time, HH:MM")
    parser.add_argument("--end", default="23:59", help="End time in Singapore time, HH:MM")
    args = parser.parse_args()

    all_rows = read_all_gold_rows()
    filtered_rows = filter_rows_by_sgt_window(
        rows=all_rows,
        report_date=args.date,
        start_time=args.start,
        end_time=args.end,
    )

    hourly_report = aggregate_hourly(filtered_rows)
    daily_report = aggregate_daily(hourly_report)

    output_dir = FINAL_REPORT_ROOT / f"date={args.date}"

    hourly_output = output_dir / f"lta_hourly_service_kpis_{args.date}.csv"
    daily_output = output_dir / f"lta_daily_service_kpis_{args.date}.csv"

    write_csv(hourly_report, hourly_output)
    write_csv(daily_report, daily_output)

    print(
        {
            "report_date": args.date,
            "input_gold_rows": len(all_rows),
            "filtered_gold_rows": len(filtered_rows),
            "hourly_report_rows": len(hourly_report),
            "daily_report_rows": len(daily_report),
            "hourly_output": str(hourly_output),
            "daily_output": str(daily_output),
        }
    )


if __name__ == "__main__":
    main()
