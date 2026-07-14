import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SILVER_ROOT = PROJECT_ROOT / "data" / "silver" / "bus_arrival"
GOLD_ROOT = PROJECT_ROOT / "data" / "gold" / "bus_arrival_kpis"

SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


def get_latest_silver_file() -> Path:
    silver_files = sorted(SILVER_ROOT.rglob("*.csv"))

    if not silver_files:
        raise FileNotFoundError(f"No silver CSV files found in {SILVER_ROOT}")

    return silver_files[-1]


def safe_float(value):
    try:
        if value in ("", None):
            return None
        return float(value)
    except ValueError:
        return None


def classify_day_type(date_value: datetime) -> str:
    # Monday = 0, Sunday = 6
    if date_value.weekday() >= 5:
        return "weekend"
    return "weekday"


def read_silver_records(silver_file: Path) -> list[dict]:
    with silver_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def aggregate_records(records: list[dict], silver_file: Path) -> list[dict]:
    groups = defaultdict(list)

    for row in records:
        key = (
            row.get("bus_stop_code", ""),
            row.get("service_no", ""),
            row.get("operator", ""),
        )
        groups[key].append(row)

    now_sgt = datetime.now(SINGAPORE_TZ)

    gold_records = []

    for (bus_stop_code, service_no, operator), rows in groups.items():
        wait_times = []

        monitored_count = 0
        unmonitored_count = 0

        sea_count = 0
        sda_count = 0
        lsd_count = 0
        unknown_load_count = 0

        single_deck_count = 0
        double_deck_count = 0
        bendy_bus_count = 0
        unknown_bus_type_count = 0

        wheelchair_accessible_count = 0

        for row in rows:
            wait_time = safe_float(row.get("wait_time_minutes"))

            if wait_time is not None:
                # For KPI reporting, negative wait time means bus is arriving/just arrived.
                wait_times.append(max(wait_time, 0))

            monitored = str(row.get("monitored", "")).strip()

            if monitored == "1":
                monitored_count += 1
            else:
                unmonitored_count += 1

            load = row.get("load", "").strip().upper()

            if load == "SEA":
                sea_count += 1
            elif load == "SDA":
                sda_count += 1
            elif load == "LSD":
                lsd_count += 1
            else:
                unknown_load_count += 1

            bus_type = row.get("bus_type", "").strip().upper()

            if bus_type == "SD":
                single_deck_count += 1
            elif bus_type == "DD":
                double_deck_count += 1
            elif bus_type == "BD":
                bendy_bus_count += 1
            else:
                unknown_bus_type_count += 1

            feature = row.get("feature", "").strip().upper()

            if feature == "WAB":
                wheelchair_accessible_count += 1

        avg_wait = round(sum(wait_times) / len(wait_times), 2) if wait_times else None
        min_wait = round(min(wait_times), 2) if wait_times else None
        max_wait = round(max(wait_times), 2) if wait_times else None

        gold_records.append(
            {
                "kpi_created_timestamp_sgt": now_sgt.isoformat(),
                "kpi_date": now_sgt.date().isoformat(),
                "kpi_hour": now_sgt.hour,
                "kpi_minute": now_sgt.minute,
                "day_name": now_sgt.strftime("%A"),
                "day_type": classify_day_type(now_sgt),
                "source_silver_file": silver_file.name,
                "bus_stop_code": bus_stop_code,
                "service_no": service_no,
                "operator": operator,
                "arrival_record_count": len(rows),
                "avg_wait_time_minutes": avg_wait,
                "min_wait_time_minutes": min_wait,
                "max_wait_time_minutes": max_wait,
                "monitored_bus_count": monitored_count,
                "unmonitored_bus_count": unmonitored_count,
                "seat_available_count": sea_count,
                "standing_available_count": sda_count,
                "limited_standing_count": lsd_count,
                "unknown_load_count": unknown_load_count,
                "single_deck_count": single_deck_count,
                "double_deck_count": double_deck_count,
                "bendy_bus_count": bendy_bus_count,
                "unknown_bus_type_count": unknown_bus_type_count,
                "wheelchair_accessible_count": wheelchair_accessible_count,
            }
        )

    return gold_records


def write_gold_csv(records: list[dict]) -> str:
    now_sgt = datetime.now(SINGAPORE_TZ)

    output_dir = (
        GOLD_ROOT
        / f"date={now_sgt.date()}"
        / f"hour={now_sgt.hour:02d}"
        / f"minute={now_sgt.minute:02d}"
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"gold_bus_arrival_kpis_{now_sgt.strftime('%Y%m%dT%H%M%S%z')}.csv"

    if not records:
        output_file.write_text("", encoding="utf-8")
        return str(output_file)

    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    return str(output_file)


def main() -> dict:
    silver_file = get_latest_silver_file()
    records = read_silver_records(silver_file)
    gold_records = aggregate_records(records, silver_file)
    gold_output = write_gold_csv(gold_records)

    result = {
        "silver_file": str(silver_file),
        "gold_output": gold_output,
        "silver_record_count": len(records),
        "gold_record_count": len(gold_records),
    }

    print(result)
    return result


if __name__ == "__main__":
    main()
