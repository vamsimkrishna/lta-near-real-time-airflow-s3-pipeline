
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
BRONZE_ROOT = PROJECT_ROOT / "data" / "bronze" / "bus_arrival"
SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


def load_env_file() -> None:
    """
    Simple .env loader using only Python standard library.
    This avoids extra dependency issues inside Airflow.
    """
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env file not found at {ENV_FILE}")

    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def fetch_bus_arrival(bus_stop_code: str, account_key: str) -> dict:
    """
    Fetch Bus Arrival data from LTA DataMall API.
    """
    base_url = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"
    query = urllib.parse.urlencode({"BusStopCode": bus_stop_code})
    url = f"{base_url}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "AccountKey": account_key,
            "accept": "application/json",
        },
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        status_code = response.status
        response_body = response.read().decode("utf-8")

    data = json.loads(response_body)

    return {
        "metadata": {
            "source": "LTA DataMall BusArrivalv3",
            "bus_stop_code": bus_stop_code,
            "ingestion_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "ingestion_timestamp_sgt": datetime.now(SINGAPORE_TZ).isoformat(),
            "http_status_code": status_code,
        },
        "raw_response": data,
    }


def write_bronze_file(payload: dict, bus_stop_code: str) -> str:
    """
    Write raw API response into Bronze folder partitioned by date/hour/minute.
    """
    now = datetime.now(SINGAPORE_TZ)

    output_dir = (
        BRONZE_ROOT
        / f"date={now.date()}"
        / f"hour={now.hour:02d}"
        / f"minute={now.minute:02d}"
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"bus_arrival_{bus_stop_code}_{now.strftime('%Y%m%dT%H%M%SZ')}.json"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return str(output_file)


def main() -> str:
    load_env_file()

    account_key = os.getenv("LTA_API_KEY")
    bus_stop_code = os.getenv("BUS_STOP_CODE", "22009")

    if not account_key or account_key == "PASTE_YOUR_LTA_API_KEY_HERE":
        raise ValueError("LTA_API_KEY is missing. Please update your .env file.")

    payload = fetch_bus_arrival(bus_stop_code=bus_stop_code, account_key=account_key)
    output_file = write_bronze_file(payload=payload, bus_stop_code=bus_stop_code)

    print(f"Bronze file written: {output_file}")
    return output_file


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Bronze ingestion failed: {e}", file=sys.stderr)
        raise
