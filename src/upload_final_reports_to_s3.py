import argparse
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
FINAL_REPORT_ROOT = PROJECT_ROOT / "data" / "final_reports"


def load_env_file() -> None:
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env file not found: {ENV_FILE}")

    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_report_files(report_date: str) -> list[Path]:
    report_dir = FINAL_REPORT_ROOT / f"date={report_date}"

    if not report_dir.exists():
        raise FileNotFoundError(f"Report folder not found: {report_dir}")

    files = sorted(report_dir.glob("*.csv"))

    if not files:
        raise FileNotFoundError(f"No CSV files found in: {report_dir}")

    return files


def create_s3_client():
    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def upload_file_to_s3(
    s3_client,
    local_file: Path,
    bucket: str,
    s3_key: str,
    dry_run: bool,
) -> None:
    if dry_run:
        print(f"[DRY RUN] {local_file} -> s3://{bucket}/{s3_key}")
        return

    try:
        s3_client.upload_file(str(local_file), bucket, s3_key)
        print(f"Uploaded: {local_file} -> s3://{bucket}/{s3_key}")
    except ClientError as error:
        print(f"Upload failed: {local_file}")
        print(error)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Report date, e.g. 2026-07-10")
    parser.add_argument("--dry-run", action="store_true", help="Show files without uploading")
    args = parser.parse_args()

    load_env_file()

    bucket = os.getenv("S3_BUCKET_NAME")
    prefix = os.getenv("S3_PREFIX", "lta-bus-arrival/final_reports").strip("/")

    if not bucket:
        raise ValueError("S3_BUCKET_NAME is missing in .env")

    report_files = get_report_files(args.date)
    total_bytes = sum(file.stat().st_size for file in report_files)

    print(
        {
            "report_date": args.date,
            "file_count": len(report_files),
            "total_size_mb": round(total_bytes / (1024 * 1024), 4),
            "bucket": bucket,
            "prefix": prefix,
            "dry_run": args.dry_run,
        }
    )

    s3_client = create_s3_client()

    for local_file in report_files:
        s3_key = f"{prefix}/date={args.date}/{local_file.name}"

        upload_file_to_s3(
            s3_client=s3_client,
            local_file=local_file,
            bucket=bucket,
            s3_key=s3_key,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
