-- Database Setup Script for Enterprise Data Lineage Platform
-- Run this script as the postgres superuser

-- Create the database
CREATE DATABASE lineage_platform;

-- Connect to the database (you'll need to do this manually in psql or pgAdmin)
-- \c lineage_platform

-- Create the user
CREATE USER lineage_user WITH PASSWORD 'password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE lineage_platform TO lineage_user;

-- Grant schema privileges (needed for PostgreSQL 15+)
\c lineage_platform
GRANT ALL ON SCHEMA public TO lineage_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO lineage_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO lineage_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO lineage_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO lineage_user;

-- =============================================================================
-- Week 2 Day 1: Schema migration helper
-- Run manually if the lineage_platform database already exists and the
-- lineage_relationships table was created before the dag_id column was added.
-- =============================================================================

-- Add dag_id column to lineage_relationships (idempotent via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name  = 'lineage_relationships'
          AND column_name = 'dag_id'
    ) THEN
        ALTER TABLE lineage_relationships
            ADD COLUMN dag_id VARCHAR(255);

        CREATE INDEX IF NOT EXISTS ix_lineage_relationships_dag_id
            ON lineage_relationships (dag_id);
    END IF;
END
$$;

-- =============================================================================
-- Sample lineage data: multi-level dependency chain
--
-- Data flow:
--   customers ─────────────────────────────────────────┐
--   orders_raw ─────┐                                  │
--                   ▼                                  ▼
--               orders ──────────────────────► sales_summary
--                   │                                  │
--                   ▼                                  ▼
--           order_items ──────────────────► monthly_report
--
-- Demonstrates:
--   * Multi-hop upstream:   monthly_report → sales_summary → orders → orders_raw
--   * Multi-hop downstream: customers → orders → sales_summary → monthly_report
--   * Column-level lineage and DAG attribution
-- =============================================================================

-- Catalogue table nodes
INSERT INTO tables (name, schema_name)
VALUES
    ('customers',      'public'),
    ('orders_raw',     'public'),
    ('orders',         'public'),
    ('order_items',    'public'),
    ('sales_summary',  'public'),
    ('monthly_report', 'public')
ON CONFLICT (name, schema_name) DO NOTHING;

-- Lineage edges
INSERT INTO lineage_relationships
    (source_table, target_table, column_name, source_column, dag_id)
VALUES
    -- customers feeds into orders
    ('customers',     'orders',         'customer_id',  'id',           'etl_pipeline'),
    -- orders_raw feeds into orders
    ('orders_raw',    'orders',         'order_amount', 'raw_amount',   'etl_pipeline'),
    -- orders feeds into sales_summary
    ('orders',        'sales_summary',  'total_amount', 'order_amount', 'etl_pipeline'),
    -- orders feeds into order_items
    ('orders',        'order_items',    'order_id',     'id',           'etl_pipeline'),
    -- sales_summary feeds into monthly_report
    ('sales_summary', 'monthly_report', 'total_sales',  'total_amount', 'reporting_pipeline'),
    -- order_items feeds into monthly_report
    ('order_items',   'monthly_report', 'item_count',   'quantity',     'reporting_pipeline');


-- =============================================================================
-- Column-level lineage table
--
-- Stores fine-grained source_col → target_col edges with an optional
-- transformation expression (SQL snippet that derives the target column).
--
-- Traversal uses WITH RECURSIVE CTEs in graph_service.py:
--   fetch_column_upstream   – walks target_col ← source_col chains
--   fetch_column_downstream – walks source_col → target_col chains
-- =============================================================================

CREATE TABLE IF NOT EXISTS column_lineage (
    id                  SERIAL PRIMARY KEY,
    source_table        VARCHAR(255) NOT NULL,
    source_column       VARCHAR(255) NOT NULL,
    target_table        VARCHAR(255) NOT NULL,
    target_column       VARCHAR(255) NOT NULL,
    transformation      TEXT,
    transformation_type VARCHAR(32)  NOT NULL DEFAULT 'DIRECT',
    dag_id              VARCHAR(255),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_column_lineage_edge
        UNIQUE (source_table, source_column, target_table, target_column)
);

CREATE INDEX IF NOT EXISTS ix_column_lineage_source
    ON column_lineage (source_table, source_column);

CREATE INDEX IF NOT EXISTS ix_column_lineage_target
    ON column_lineage (target_table, target_column);

CREATE INDEX IF NOT EXISTS ix_column_lineage_dag_id
    ON column_lineage (dag_id);

CREATE INDEX IF NOT EXISTS ix_column_lineage_type
    ON column_lineage (transformation_type);

GRANT ALL PRIVILEGES ON TABLE column_lineage TO lineage_user;
GRANT USAGE, SELECT ON SEQUENCE column_lineage_id_seq TO lineage_user;

-- Idempotent migration: add transformation_type to pre-existing column_lineage tables
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'column_lineage' AND column_name = 'transformation_type'
    ) THEN
        ALTER TABLE column_lineage
            ADD COLUMN transformation_type VARCHAR(32) NOT NULL DEFAULT 'DIRECT';
    END IF;
END
$$;

-- =============================================================================
-- Sample column-level lineage data
--
-- Mirrors the table-level lineage sample data above at column granularity.
--
-- Data flow (column level):
--   customers.id          ──► orders.customer_id
--   orders_raw.raw_amount ──► orders.order_amount
--   orders.order_amount   ──► sales_summary.total_amount   (SUM)
--   orders.id             ──► order_items.order_id
--   sales_summary.total_amount ──► monthly_report.total_sales
--   order_items.quantity  ──► monthly_report.item_count    (SUM)
-- =============================================================================

INSERT INTO column_lineage
    (source_table, source_column, target_table, target_column, transformation, transformation_type, dag_id)
VALUES
    ('customers',     'id',           'orders',         'customer_id',  NULL,                       'DIRECT',        'etl_pipeline'),
    ('orders_raw',    'raw_amount',   'orders',         'order_amount', NULL,                       'DIRECT',        'etl_pipeline'),
    ('orders',        'order_amount', 'sales_summary',  'total_amount', 'SUM(orders.order_amount)', 'AGGREGATE_SUM', 'etl_pipeline'),
    ('orders',        'id',           'order_items',    'order_id',     NULL,                       'DIRECT',        'etl_pipeline'),
    ('sales_summary', 'total_amount', 'monthly_report', 'total_sales',  NULL,                       'DIRECT',        'reporting_pipeline'),
    ('order_items',   'quantity',     'monthly_report', 'item_count',   'SUM(order_items.quantity)','AGGREGATE_SUM', 'reporting_pipeline')
ON CONFLICT ON CONSTRAINT uq_column_lineage_edge DO NOTHING;
