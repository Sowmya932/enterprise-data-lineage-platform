"""
etl_pipeline_dag.py
-------------------
Daily ETL pipeline DAG.

Flow:
    extract_raw_data >> validate_raw_data >> transform_data >> load_to_warehouse
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


# ---------------------------------------------------------------------------
# Default arguments applied to every task unless overridden
# ---------------------------------------------------------------------------
default_args = {
    "owner": "data_engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# SQL used by each task (embedded as strings for lineage tracing)
# ---------------------------------------------------------------------------
EXTRACT_SQL = """
INSERT INTO staging.raw_orders
SELECT
    order_id,
    customer_id,
    product_id,
    quantity,
    unit_price,
    order_date,
    status
FROM source.orders
WHERE order_date = CURRENT_DATE - INTERVAL '1 day';
"""

TRANSFORM_SQL = """
INSERT INTO staging.transformed_orders
SELECT
    order_id,
    customer_id,
    product_id,
    quantity,
    unit_price,
    quantity * unit_price          AS total_amount,
    UPPER(status)                  AS status_normalized,
    order_date
FROM staging.raw_orders
WHERE status NOT IN ('CANCELLED', 'RETURNED');
"""

LOAD_SQL = """
INSERT INTO warehouse.fact_orders
SELECT
    order_id,
    customer_id,
    product_id,
    quantity,
    unit_price,
    total_amount,
    status_normalized  AS status,
    order_date,
    NOW()              AS loaded_at
FROM staging.transformed_orders;
"""


# ---------------------------------------------------------------------------
# Python callables
# ---------------------------------------------------------------------------
def extract_raw_data_fn(**context):
    """Extract yesterday's orders from the source system into the staging layer."""
    print(f"[extract_raw_data] Extracting data for logical date: {context['ds']}")
    print(f"SQL:\n{EXTRACT_SQL}")


def validate_raw_data_fn(**context):
    """Run data-quality checks on the staged raw rows."""
    print(f"[validate_raw_data] Validating staged data for: {context['ds']}")
    # Example: assert no NULLs in order_id, non-negative quantities, etc.


def transform_data_fn(**context):
    """Apply business-rule transformations."""
    print(f"[transform_data] Transforming data for: {context['ds']}")
    print(f"SQL:\n{TRANSFORM_SQL}")


def load_to_warehouse_fn(**context):
    """Load transformed rows into the warehouse fact table."""
    print(f"[load_to_warehouse] Loading data for: {context['ds']}")
    print(f"SQL:\n{LOAD_SQL}")


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="daily_etl_pipeline",
    default_args=default_args,
    description="Daily ETL: extract → validate → transform → load to warehouse",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "daily", "orders"],
) as dag:

    extract_raw_data = PythonOperator(
        task_id="extract_raw_data",
        python_callable=extract_raw_data_fn,
        sql=EXTRACT_SQL,
    )

    validate_raw_data = PythonOperator(
        task_id="validate_raw_data",
        python_callable=validate_raw_data_fn,
    )

    transform_data = PythonOperator(
        task_id="transform_data",
        python_callable=transform_data_fn,
        sql=TRANSFORM_SQL,
    )

    load_to_warehouse = PythonOperator(
        task_id="load_to_warehouse",
        python_callable=load_to_warehouse_fn,
        sql=LOAD_SQL,
    )

    # Task dependency chain
    extract_raw_data >> validate_raw_data >> transform_data >> load_to_warehouse
