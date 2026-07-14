import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BRONZE_ROOT = PROJECT_ROOT / "data" / "bronze" / "bus_arrival"
SILVER_ROOT = PROJECT_ROOT / "data" / "silver" / "bus_arrival"
REJECTED_ROOT = PROJECT_ROOT / "data" / "rejected" / "bad_records"
SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


def get_latest_bronze_file() -> Path:
    bronze_files = sorted(BRONZE_ROOT.rglob("*.json"))

    if not bronze_files:
        raise FileNotFoundError(f"No bronze JSON files found in {BRONZE_ROOT}")

    return bronze_files[-1]


def parse_datetime(value: str):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def calculate_wait_minutes(ingestion_timestamp_utc: str, estimated_arrival: str):
    ingestion_dt = datetime.fromisoformat(ingestion_timestamp_utc)
    arrival_dt = parse_datetime(estimated_arrival)

    if arrival_dt is None:
        return None

    if ingestion_dt.tzinfo is None:
        ingestion_dt = ingestion_dt.replace(tzinfo=timezone.utc)

    wait_seconds = (arrival_dt.astimezone(timezone.utc) - ingestion_dt).total_seconds()
    return round(wait_seconds / 60, 2)


def validate_record(record: dict) -> tuple[bool, str]:
    if not record["service_no"]:
        return False, "missing_service_no"

    if not record["estimated_arrival"]:
        return False, "missing_estimated_arrival"

    if record["wait_time_minutes"] is None:
        return False, "invalid_estimated_arrival"

    if record["wait_time_minutes"] < -5:
        return False, "arrival_time_too_old"

    return True, ""


def flatten_bronze_file(bronze_file: Path) -> tuple[list[dict], list[dict]]:
    with bronze_file.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    metadata = payload.get("metadata", {})
    raw_response = payload.get("raw_response", {})

    ingestion_timestamp_utc = metadata.get("ingestion_timestamp_utc")
    bus_stop_code = raw_response.get("BusStopCode") or metadata.get("bus_stop_code")
    services = raw_response.get("Services", [])

    valid_records = []
    rejected_records = []

    for service in services:
        service_no = service.get("ServiceNo")
        operator = service.get("Operator")

        for bus_sequence, bus_key in enumerate(["NextBus", "NextBus2", "NextBus3"], start=1):
            bus = service.get(bus_key, {})

            estimated_arrival = bus.get("EstimatedArrival", "")
            wait_time_minutes = calculate_wait_minutes(
                ingestion_timestamp_utc=ingestion_timestamp_utc,
                estimated_arrival=estimated_arrival,
            )

            record = {
                "ingestion_timestamp_utc": ingestion_timestamp_utc,
                "bronze_file_name": bronze_file.name,
                "bus_stop_code": bus_stop_code,
                "service_no": service_no,
                "operator": operator,
                "bus_sequence": bus_sequence,
                "origin_code": bus.get("OriginCode", ""),
                "destination_code": bus.get("DestinationCode", ""),
                "estimated_arrival": estimated_arrival,
                "wait_time_minutes": wait_time_minutes,
                "monitored": bus.get("Monitored", ""),
                "latitude": bus.get("Latitude", ""),
                "longitude": bus.get("Longitude", ""),
                "visit_number": bus.get("VisitNumber", ""),
                "load": bus.get("Load", ""),
                "feature": bus.get("Feature", ""),
                "bus_type": bus.get("Type", ""),
            }

            is_valid, validation_error = validate_record(record)

            if is_valid:
                record["is_valid"] = True
                record["validation_error"] = ""
                valid_records.append(record)
            else:
                record["is_valid"] = False
                record["validation_error"] = validation_error
                rejected_records.append(record)

    return valid_records, rejected_records


def write_csv(records: list[dict], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not records:
        output_file.write_text("", encoding="utf-8")
        return

    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def main() -> dict:
    bronze_file = get_latest_bronze_file()
    valid_records, rejected_records = flatten_bronze_file(bronze_file)

    now = datetime.now(SINGAPORE_TZ)
    partition_path = f"date={now.date()}/hour={now.hour:02d}/minute={now.minute:02d}"

    silver_output = SILVER_ROOT / partition_path / f"silver_bus_arrival_{now.strftime('%Y%m%dT%H%M%SZ')}.csv"
    rejected_output = REJECTED_ROOT / partition_path / f"rejected_bus_arrival_{now.strftime('%Y%m%dT%H%M%SZ')}.csv"

    write_csv(valid_records, silver_output)
    write_csv(rejected_records, rejected_output)

    result = {
        "bronze_file": str(bronze_file),
        "silver_output": str(silver_output),
        "rejected_output": str(rejected_output),
        "valid_record_count": len(valid_records),
        "rejected_record_count": len(rejected_records),
    }

    print(result)
    return result


if __name__ == "__main__":
    main()
