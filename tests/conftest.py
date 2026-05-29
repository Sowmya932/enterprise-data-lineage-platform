"""
conftest.py
-----------
Pytest configuration and shared fixtures for all tests.

Fixtures provide:
- Database setup/teardown with test database
- FastAPI test client
- Sample data for testing
- Mock dependencies
"""

import pytest
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.db import Base, get_db
from backend.database.orm_models import TableRecord, LineageRelationship, ColumnLineage


# Use in-memory SQLite for fast tests
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def test_session_factory(test_engine):
    """Create a test session factory."""
    return sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest.fixture
def test_db(test_session_factory):
    """Provide a fresh test database session for each test."""
    connection = test_session_factory.kw["bind"].connect()
    transaction = connection.begin()
    session = test_session_factory(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(test_db):
    """Provide a FastAPI test client with test database dependency."""
    def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ============================================================
# Sample Data Fixtures
# ============================================================

@pytest.fixture
def sample_tables(test_db):
    """Create sample table records for testing."""
    tables = [
        TableRecord(name="customers", schema_name="public"),
        TableRecord(name="orders", schema_name="public"),
        TableRecord(name="products", schema_name="public"),
        TableRecord(name="order_details", schema_name="public"),
        TableRecord(name="customer_analytics", schema_name="analytics"),
        TableRecord(name="revenue_summary", schema_name="analytics"),
    ]
    
    test_db.add_all(tables)
    test_db.commit()
    
    # Refresh to get IDs
    for table in tables:
        test_db.refresh(table)
    
    return {t.name: t for t in tables}


@pytest.fixture
def sample_lineage_relationships(test_db, sample_tables):
    """Create sample lineage relationships for testing."""
    relationships = [
        LineageRelationship(
            source_table="customers",
            target_table="customer_analytics",
            dag_id="etl_pipeline",
        ),
        LineageRelationship(
            source_table="orders",
            target_table="customer_analytics",
            dag_id="etl_pipeline",
        ),
        LineageRelationship(
            source_table="orders",
            target_table="order_details",
            dag_id="load_pipeline",
        ),
        LineageRelationship(
            source_table="products",
            target_table="order_details",
            dag_id="load_pipeline",
        ),
        LineageRelationship(
            source_table="customer_analytics",
            target_table="revenue_summary",
            dag_id="reporting_pipeline",
        ),
    ]
    
    test_db.add_all(relationships)
    test_db.commit()
    
    for rel in relationships:
        test_db.refresh(rel)
    
    return relationships


@pytest.fixture
def sample_column_lineage(test_db, sample_tables):
    """Create sample column-level lineage for testing."""
    columns = [
        ColumnLineage(
            source_table="customers",
            source_column="customer_id",
            target_table="customer_analytics",
            target_column="customer_id",
            transformation="DIRECT",
            transformation_type="DIRECT",
        ),
        ColumnLineage(
            source_table="customers",
            source_column="customer_name",
            target_table="customer_analytics",
            target_column="customer_name",
            transformation="DIRECT",
            transformation_type="DIRECT",
        ),
        ColumnLineage(
            source_table="orders",
            source_column="order_amount",
            target_table="customer_analytics",
            target_column="total_spend",
            transformation="SUM(order_amount)",
            transformation_type="AGGREGATION",
        ),
        ColumnLineage(
            source_table="customer_analytics",
            source_column="total_spend",
            target_table="revenue_summary",
            target_column="total_revenue",
            transformation="SUM(total_spend)",
            transformation_type="AGGREGATION",
        ),
    ]
    
    test_db.add_all(columns)
    test_db.commit()
    
    for col in columns:
        test_db.refresh(col)
    
    return columns


# ============================================================
# Mock Data Fixtures
# ============================================================

@pytest.fixture
def sample_sql_queries():
    """Provide sample SQL queries for testing."""
    return {
        "simple_select": "SELECT * FROM customers WHERE id > 100;",
        "simple_insert": "INSERT INTO customers (name, email) VALUES ('John', 'john@example.com');",
        "simple_update": "UPDATE orders SET status = 'completed' WHERE order_id = 123;",
        "simple_delete": "DELETE FROM orders WHERE order_date < '2020-01-01';",
        "join_query": """
            SELECT 
                c.customer_id, 
                c.customer_name, 
                COUNT(o.order_id) as order_count
            FROM customers c
            LEFT JOIN orders o ON c.customer_id = o.customer_id
            GROUP BY c.customer_id, c.customer_name;
        """,
        "subquery": """
            SELECT customer_id, order_amount
            FROM orders
            WHERE customer_id IN (
                SELECT customer_id FROM customers WHERE country = 'USA'
            );
        """,
        "cte_query": """
            WITH customer_orders AS (
                SELECT customer_id, COUNT(*) as order_count
                FROM orders
                GROUP BY customer_id
            )
            SELECT c.customer_name, co.order_count
            FROM customers c
            JOIN customer_orders co ON c.customer_id = co.customer_id;
        """,
    }


@pytest.fixture
def sample_dag_content():
    """Provide sample Airflow DAG code for testing."""
    return """
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def extract_task():
    pass

def transform_task():
    pass

def load_task():
    pass

with DAG(
    'etl_pipeline',
    start_date=datetime(2024, 1, 1),
    schedule_interval='@daily'
) as dag:
    extract = PythonOperator(task_id='extract', python_callable=extract_task)
    transform = PythonOperator(task_id='transform', python_callable=transform_task)
    load = PythonOperator(task_id='load', python_callable=load_task)
    
    extract >> transform >> load
"""


# ============================================================
# Marker Registration
# ============================================================

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "db: mark test as requiring database access"
    )
