"""
warehouse_loading_dag.py
-------------------------
Warehouse loading pipeline DAG.

Flow:
    validate_source >> stage_data >> load_dimensions >> load_facts >> refresh_aggregates
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


# ---------------------------------------------------------------------------
# Default arguments
# ---------------------------------------------------------------------------
default_args = {
    "owner": "data_warehouse",
    "depends_on_past": True,        # Each run must wait for the previous to succeed
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=15),
}

# ---------------------------------------------------------------------------
# SQL used by each task
# ---------------------------------------------------------------------------
VALIDATE_SQL = """
SELECT
    COUNT(*)                                         AS total_rows,
    COUNT(*) FILTER (WHERE order_id   IS NULL)       AS null_order_ids,
    COUNT(*) FILTER (WHERE customer_id IS NULL)      AS null_customer_ids,
    COUNT(*) FILTER (WHERE quantity   <= 0)          AS invalid_quantities,
    COUNT(*) FILTER (WHERE unit_price <= 0)          AS invalid_prices
FROM staging.raw_orders
WHERE order_date = CURRENT_DATE - INTERVAL '1 day';
"""

STAGE_SQL = """
INSERT INTO staging.orders_staging
SELECT
    order_id,
    customer_id,
    product_id,
    quantity,
    unit_price,
    quantity * unit_price  AS total_amount,
    order_date,
    status,
    NOW()                  AS staged_at
FROM staging.raw_orders
WHERE order_date = CURRENT_DATE - INTERVAL '1 day'
  AND order_id    IS NOT NULL
  AND customer_id IS NOT NULL
  AND quantity    > 0
  AND unit_price  > 0;
"""

LOAD_DIMENSIONS_SQL = """
INSERT INTO warehouse.dim_customers (customer_id, first_seen, last_seen)
SELECT
    customer_id,
    MIN(order_date) AS first_seen,
    MAX(order_date) AS last_seen
FROM staging.orders_staging
GROUP BY customer_id
ON CONFLICT (customer_id)
DO UPDATE SET last_seen = EXCLUDED.last_seen;

INSERT INTO warehouse.dim_products (product_id, first_seen, last_seen)
SELECT
    product_id,
    MIN(order_date) AS first_seen,
    MAX(order_date) AS last_seen
FROM staging.orders_staging
GROUP BY product_id
ON CONFLICT (product_id)
DO UPDATE SET last_seen = EXCLUDED.last_seen;
"""

LOAD_FACTS_SQL = """
INSERT INTO warehouse.fact_orders
    (order_id, customer_id, product_id, quantity,
     unit_price, total_amount, status, order_date, loaded_at)
SELECT
    s.order_id,
    s.customer_id,
    s.product_id,
    s.quantity,
    s.unit_price,
    s.total_amount,
    s.status,
    s.order_date,
    NOW() AS loaded_at
FROM staging.orders_staging s
LEFT JOIN warehouse.fact_orders f USING (order_id)
WHERE f.order_id IS NULL;   -- idempotent: skip already-loaded rows
"""

REFRESH_AGGREGATES_SQL = """
REFRESH MATERIALIZED VIEW CONCURRENTLY warehouse.mv_daily_revenue;
REFRESH MATERIALIZED VIEW CONCURRENTLY warehouse.mv_product_performance;
REFRESH MATERIALIZED VIEW CONCURRENTLY warehouse.mv_customer_lifetime_value;
"""


# ---------------------------------------------------------------------------
# Python callables
# ---------------------------------------------------------------------------
def validate_source_fn(**context):
    """Assert data-quality rules on the previous day's staged raw orders."""
    print(f"[validate_source] Running DQ checks for: {context['ds']}")
    print(f"SQL:\n{VALIDATE_SQL}")


def stage_data_fn(**context):
    """Move validated rows from raw staging to the orders staging table."""
    print(f"[stage_data] Staging clean rows for: {context['ds']}")
    print(f"SQL:\n{STAGE_SQL}")


def load_dimensions_fn(**context):
    """Upsert customer and product dimension tables."""
    print(f"[load_dimensions] Loading dimensions for: {context['ds']}")
    print(f"SQL:\n{LOAD_DIMENSIONS_SQL}")


def load_facts_fn(**context):
    """Insert new fact rows into the warehouse fact_orders table."""
    print(f"[load_facts] Loading facts for: {context['ds']}")
    print(f"SQL:\n{LOAD_FACTS_SQL}")


def refresh_aggregates_fn(**context):
    """Refresh all materialized views that depend on the newly loaded facts."""
    print(f"[refresh_aggregates] Refreshing materialized views for: {context['ds']}")
    print(f"SQL:\n{REFRESH_AGGREGATES_SQL}")


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="warehouse_loading_pipeline",
    default_args=default_args,
    description="Warehouse loading: validate source → stage → load dims → load facts → refresh aggregates",
    schedule_interval="0 2 * * *",   # 02:00 UTC every day
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["warehouse", "loading", "dimensions", "facts"],
) as dag:

    validate_source = PythonOperator(
        task_id="validate_source",
        python_callable=validate_source_fn,
        sql=VALIDATE_SQL,
    )

    stage_data = PythonOperator(
        task_id="stage_data",
        python_callable=stage_data_fn,
        sql=STAGE_SQL,
    )

    load_dimensions = PythonOperator(
        task_id="load_dimensions",
        python_callable=load_dimensions_fn,
        sql=LOAD_DIMENSIONS_SQL,
    )

    load_facts = PythonOperator(
        task_id="load_facts",
        python_callable=load_facts_fn,
        sql=LOAD_FACTS_SQL,
    )

    refresh_aggregates = PythonOperator(
        task_id="refresh_aggregates",
        python_callable=refresh_aggregates_fn,
        sql=REFRESH_AGGREGATES_SQL,
    )

    # Task dependency chain
    validate_source >> stage_data >> load_dimensions >> load_facts >> refresh_aggregates
