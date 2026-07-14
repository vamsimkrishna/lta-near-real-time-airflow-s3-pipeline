import sys
from datetime import datetime, time, date
from zoneinfo import ZoneInfo

import pendulum
from airflow.decorators import dag, task


PROJECT_ROOT = "/home/vamsi/projects/lta-airflow-project"
SINGAPORE_TZ = ZoneInfo("Asia/Singapore")

COLLECTION_START_DATE = date(2026, 7, 10)
COLLECTION_END_DATE = date(2026, 7, 12)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@dag(
    dag_id="lta_minutely_bus_arrival_pipeline",
    description="3-day LTA Bus Arrival pipeline: Bronze raw ingestion and Silver validation",
    start_date=pendulum.datetime(2026, 7, 10, 5, 0, tz="Asia/Singapore"),
    end_date=pendulum.datetime(2026, 7, 12, 23, 59, tz="Asia/Singapore"),
    schedule="* 5-23 * * *",
    catchup=False,
    tags=["lta", "bus-arrival", "bronze", "silver", "3-day-analysis"],
)
def lta_minutely_bus_arrival_pipeline():

    @task
    def check_collection_window() -> str:
        now_sgt = datetime.now(SINGAPORE_TZ)
        current_date = now_sgt.date()
        current_time = now_sgt.time()

        if not (COLLECTION_START_DATE <= current_date <= COLLECTION_END_DATE):
            raise ValueError(
                f"Outside collection dates. Current date: {current_date}. "
                f"Allowed: {COLLECTION_START_DATE} to {COLLECTION_END_DATE}"
            )

        if not (time(5, 0) <= current_time <= time(23, 59, 59)):
            raise ValueError(
                f"Outside operating window. Current time: {current_time}. "
                "Allowed: 05:00 to 23:59 Singapore time."
            )

        return (
            f"Inside collection window: {current_date} "
            f"{current_time.strftime('%H:%M:%S')} Singapore time"
        )

    @task
    def fetch_to_bronze() -> str:
        from src.fetch_lta_bronze import main
        return main()

    @task
    def transform_bronze_to_silver() -> dict:
        from src.bronze_to_silver import main
        return main()

    @task
    def aggregate_silver_to_gold() -> dict:
        from src.silver_to_gold import main
        return main()

    check_collection_window() >> fetch_to_bronze() >> transform_bronze_to_silver() >> aggregate_silver_to_gold()


lta_minutely_bus_arrival_pipeline()
