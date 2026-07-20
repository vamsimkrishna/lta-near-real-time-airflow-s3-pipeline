# LTA Near Real-Time Airflow S3 Pipeline

## Overview

This project is a near real-time data engineering pipeline built using Apache Airflow, Python, and AWS S3.

The pipeline collects Singapore LTA Bus Arrival data every minute, processes it through Bronze, Silver, and Gold layers, generates final daily KPI reports, and uploads only the final reports to AWS S3.

## Project Objective

The goal of this project is to simulate a production-style data pipeline for public transport data.

The pipeline answers questions such as:

- How do bus waiting times differ between weekday and weekend?
- Which bus services have higher average waiting time?
- How does bus load pattern change by day?
- How many buses are monitored versus unmonitored?
- What is the difference between Friday, Saturday, and Sunday bus patterns?

## Architecture

```text
LTA DataMall Bus Arrival API
        ↓
Apache Airflow DAG - every minute
        ↓
Bronze Layer
Raw JSON API responses
        ↓
Silver Layer
Cleaned and flattened bus arrival records
        ↓
Gold Layer
Minute-level service KPI records
        ↓
Daily KPI Report Script
Hourly and daily service KPI reports
        ↓
AWS S3
Final reports uploaded by date partition

##Tech Stack
Python
Apache Airflow
AWS S3
boto3
CSV-based local data lake
Git and GitHub
Medallion Architecture
Bronze Layer

The Bronze layer stores raw API responses exactly as received from LTA DataMall.

##Example local path:

data/bronze/bus_arrival/date=2026-07-10/hour=05/minute=00/
Silver Layer

The Silver layer stores cleaned and flattened bus arrival records.

Each row represents one bus arrival record from:

NextBus
NextBus2
NextBus3
Gold Layer

##The Gold layer stores minute-level service KPI records.

Gold aggregates Silver rows by:

bus_stop_code
service_no
operator
minute
Final Reports

##The final report step reads all Gold files for each day and generates:

lta_hourly_service_kpis_YYYY-MM-DD.csv
lta_daily_service_kpis_YYYY-MM-DD.csv

Only these final reports are uploaded to AWS S3.

##Airflow DAG

Main DAG:

lta_minutely_bus_arrival_pipeline

Task flow:

check_collection_window
        ↓
fetch_to_bronze
        ↓
transform_bronze_to_silver
        ↓
aggregate_silver_to_gold

##Schedule:

Every minute from 05:00 AM to 11:59 PM Singapore time
Data Collection Window

##The project collected 3 days of data:

Date	Day	Type
2026-07-10	Friday	Weekday
2026-07-11	Saturday	Weekend
2026-07-12	Sunday	Weekend

Known note:

A small Friday morning maintenance gap occurred around 06:20–06:28 Singapore time because the DAG was paused to fix timezone partitioning.

A final boundary run at 23:59 initially failed because the time check used 23:59:00 instead of allowing the full 23:59 minute. This was fixed by updating the collection window to allow up to 23:59:59.

##KPI Report Summary
Date	Day	Services	API Pull Count	Arrival Records	Weighted Avg Wait
2026-07-10	Friday	31	28,715	82,591	15.18 min
2026-07-11	Saturday	27	28,193	78,932	17.35 min
2026-07-12	Sunday	27	28,032	75,486	18.54 min

##Key Observation

Friday had the highest number of arrival records and the lowest average waiting time.

Sunday had the lowest number of arrival records and the highest average waiting time.

This suggests a visible weekday versus weekend pattern in the collected LTA Bus Arrival data.

##AWS S3 Output

Final reports were uploaded to AWS S3 using date-partitioned folders:

s3://bucket-name/lta-bus-arrival/final_reports/date=2026-07-10/
s3://bucket-name/lta-bus-arrival/final_reports/date=2026-07-11/
s3://bucket-name/lta-bus-arrival/final_reports/date=2026-07-12/

##Each date folder contains:

lta_daily_service_kpis_YYYY-MM-DD.csv
lta_hourly_service_kpis_YYYY-MM-DD.csv
Screenshots
Airflow DAG List

Airflow DAG Graph / Calendar View

Airflow Successful Run

AWS S3 Final Reports

AWS S3 Report Files

##Project Structure

lta-airflow-project/
│
├── dags/
│   └── lta_minutely_bus_arrival_dag.py
│
├── src/
│   ├── fetch_lta_bronze.py
│   ├── bronze_to_silver.py
│   ├── silver_to_gold.py
│   ├── daily_kpi_report.py
│   └── upload_final_reports_to_s3.py
│
├── docs/
│   └── screenshots/
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md

##How to Run

Install dependencies:

pip install -r requirements.txt

Create .env from .env.example:

cp .env.example .env

Update .env with your LTA API key and AWS S3 details.

Start Airflow:

airflow standalone

Open the Airflow UI:

http://localhost:8080

Trigger or unpause the DAG from the Airflow UI.


GitHub Safety

The repository excludes sensitive and generated files:

.env
.venv/
airflow/
logs/
data/

Only code, configuration templates, screenshots, and documentation are committed.
 Currently building visualization for this 3 day data to show the anomalies and the operational output.

Author

Vamsi Krishna
Data Engineering Portfolio Project
Singapore
