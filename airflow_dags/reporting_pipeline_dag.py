"""
reporting_pipeline_dag.py
--------------------------
Weekly reporting pipeline DAG.

Flow:
    aggregate_metrics >> generate_reports >> validate_reports >> send_notifications
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


# ---------------------------------------------------------------------------
# Default arguments
# ---------------------------------------------------------------------------
default_args = {
    "owner": "analytics",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

# ---------------------------------------------------------------------------
# SQL used by each task
# ---------------------------------------------------------------------------
AGGREGATE_SQL = """
INSERT INTO reporting.weekly_sales_summary
SELECT
    DATE_TRUNC('week', order_date)  AS week_start,
    customer_id,
    product_id,
    SUM(quantity)                   AS total_quantity,
    SUM(total_amount)               AS total_revenue,
    COUNT(order_id)                 AS order_count,
    AVG(unit_price)                 AS avg_unit_price
FROM warehouse.fact_orders
WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE - INTERVAL '7 days')
  AND order_date <  DATE_TRUNC('week', CURRENT_DATE)
GROUP BY
    DATE_TRUNC('week', order_date),
    customer_id,
    product_id;
"""

GENERATE_REPORT_SQL = """
INSERT INTO reporting.weekly_executive_report
SELECT
    week_start,
    SUM(total_revenue)    AS gross_revenue,
    SUM(order_count)      AS total_orders,
    COUNT(DISTINCT customer_id) AS unique_customers,
    SUM(total_quantity)   AS units_sold
FROM reporting.weekly_sales_summary
WHERE week_start = DATE_TRUNC('week', CURRENT_DATE - INTERVAL '7 days')
GROUP BY week_start;
"""

VALIDATE_REPORT_SQL = """
SELECT
    week_start,
    gross_revenue,
    total_orders,
    unique_customers,
    units_sold,
    CASE
        WHEN gross_revenue <= 0 THEN 'INVALID: zero or negative revenue'
        WHEN total_orders   <= 0 THEN 'INVALID: zero orders'
        ELSE 'OK'
    END AS validation_status
FROM reporting.weekly_executive_report
WHERE week_start = DATE_TRUNC('week', CURRENT_DATE - INTERVAL '7 days');
"""


# ---------------------------------------------------------------------------
# Python callables
# ---------------------------------------------------------------------------
def aggregate_metrics_fn(**context):
    """Aggregate raw order data into weekly summary metrics."""
    print(f"[aggregate_metrics] Aggregating for week of: {context['ds']}")
    print(f"SQL:\n{AGGREGATE_SQL}")


def generate_reports_fn(**context):
    """Build the executive-level weekly report from aggregated metrics."""
    print(f"[generate_reports] Generating report for week of: {context['ds']}")
    print(f"SQL:\n{GENERATE_REPORT_SQL}")


def validate_reports_fn(**context):
    """Run sanity checks on the generated report rows."""
    print(f"[validate_reports] Validating report for week of: {context['ds']}")
    print(f"SQL:\n{VALIDATE_REPORT_SQL}")


def send_notifications_fn(**context):
    """Dispatch email / Slack notifications with the report link."""
    print(f"[send_notifications] Sending report notifications for: {context['ds']}")


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="weekly_reporting_pipeline",
    default_args=default_args,
    description="Weekly reporting: aggregate metrics → generate reports → validate → notify",
    schedule_interval="@weekly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["reporting", "weekly", "analytics"],
) as dag:

    aggregate_metrics = PythonOperator(
        task_id="aggregate_metrics",
        python_callable=aggregate_metrics_fn,
        sql=AGGREGATE_SQL,
    )

    generate_reports = PythonOperator(
        task_id="generate_reports",
        python_callable=generate_reports_fn,
        sql=GENERATE_REPORT_SQL,
    )

    validate_reports = PythonOperator(
        task_id="validate_reports",
        python_callable=validate_reports_fn,
        sql=VALIDATE_REPORT_SQL,
    )

    send_notifications = PythonOperator(
        task_id="send_notifications",
        python_callable=send_notifications_fn,
    )

    # Task dependency chain
    aggregate_metrics >> generate_reports >> validate_reports >> send_notifications
