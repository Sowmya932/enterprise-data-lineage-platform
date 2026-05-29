# Enterprise Data Lineage Platform - API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Authentication](#authentication)
4. [Error Handling](#error-handling)
5. [API Endpoints](#api-endpoints)
6. [Examples](#examples)
7. [Rate Limiting](#rate-limiting)

## Overview

The Enterprise Data Lineage Platform API provides REST endpoints for:
- SQL query parsing and lineage extraction
- Airflow DAG parsing and dependency tracking
- Table and column-level lineage management
- Recursive lineage traversal (upstream/downstream)
- Impact analysis for data changes
- Metadata search across the platform

**Base URL:** `http://localhost:8000`

**API Version:** 2.3.0

**Documentation:** `http://localhost:8000/docs` (Swagger UI)

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL 12+
- FastAPI and dependencies installed

### Starting the Server

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:45.123456",
  "version": "2.3.0"
}
```

## Authentication

Currently, the API does not require authentication. All endpoints are publicly accessible.

Future versions will support:
- API keys
- OAuth 2.0
- JWT tokens

## Error Handling

All errors follow a standardized error response format:

### Error Response Format

```json
{
  "success": false,
  "error_code": "INVALID_TABLE_NAME",
  "error_message": "Invalid table name: 'table@123'",
  "severity": "LOW",
  "details": [
    {
      "field": "table_name",
      "message": "Table name contains invalid characters",
      "value": "table@123"
    }
  ],
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| INVALID_INPUT | 400 | Request validation failed |
| INVALID_TABLE_NAME | 400 | Table name is invalid |
| INVALID_COLUMN_NAME | 400 | Column name is invalid |
| SQL_PARSE_ERROR | 422 | SQL parsing failed |
| TABLE_NOT_FOUND | 404 | Referenced table not found |
| DATABASE_ERROR | 500 | Database operation failed |
| CIRCULAR_DEPENDENCY_DETECTED | 409 | Circular dependency detected |
| INTERNAL_SERVER_ERROR | 500 | Unexpected server error |

## API Endpoints

### Health Check

#### GET /health

Check if the API is running.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:45.123456",
  "version": "2.3.0"
}
```

### SQL Lineage Parsing

#### POST /parse-sql

Parse a SQL query and extract table lineage metadata.

**Request Body:**
```json
{
  "sql": "SELECT * FROM customers WHERE id > 100;",
  "dialect": "postgres"
}
```

**Parameters:**
- `sql` (string, required): SQL query to parse
- `dialect` (string, optional): SQL dialect - "postgres", "mysql", "snowflake", "bigquery" (default: "postgres")

**Response (200 OK):**
```json
{
  "success": true,
  "lineage": {
    "target_table": null,
    "source_tables": ["customers"],
    "column_lineage": null
  },
  "raw_sql": "SELECT * FROM customers WHERE id > 100;"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/parse-sql \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT c.id, o.amount FROM customers c JOIN orders o ON c.id = o.customer_id;",
    "dialect": "postgres"
  }'
```

### Lineage Relationships

#### POST /lineage-relationship

Create a new lineage relationship (table-to-table edge).

**Request Body:**
```json
{
  "source_table": "customers",
  "target_table": "customer_analytics",
  "dag_id": "etl_pipeline",
  "column_name": null,
  "source_column": null
}
```

**Response (201 Created):**
```json
{
  "id": 42,
  "source_table": "customers",
  "target_table": "customer_analytics",
  "dag_id": "etl_pipeline",
  "created_at": "2024-01-15T10:30:45.123456"
}
```

**Error (422 Unprocessable Entity):**
```json
{
  "success": false,
  "error_code": "INVALID_INPUT",
  "error_message": "source_table and target_table must be different.",
  "severity": "LOW"
}
```

#### GET /upstream/{table_name}

Get all tables that feed into a given table (recursive upstream lineage).

**Parameters:**
- `table_name` (path parameter): Table to analyze
- `max_depth` (query parameter, optional): Maximum traversal depth (1-50, default: 10)

**Response (200 OK):**
```json
{
  "table": "customer_analytics",
  "direction": "upstream",
  "depth_limit": 10,
  "total_edges": 3,
  "upstream_tables": ["customers", "orders", "products"],
  "lineage_chain": [
    {
      "source_table": "customers",
      "target_table": "customer_analytics",
      "depth": 1
    },
    {
      "source_table": "orders",
      "target_table": "customer_analytics",
      "depth": 1
    }
  ]
}
```

**Example:**
```bash
curl "http://localhost:8000/upstream/customer_analytics?max_depth=10"
```

#### GET /downstream/{table_name}

Get all tables that depend on a given table (recursive downstream lineage).

**Parameters:**
- `table_name` (path parameter): Table to analyze
- `max_depth` (query parameter, optional): Maximum traversal depth (1-50, default: 10)

**Response (200 OK):**
```json
{
  "table": "orders",
  "direction": "downstream",
  "depth_limit": 10,
  "total_edges": 2,
  "downstream_tables": ["order_analytics", "revenue_summary"],
  "lineage_chain": [
    {
      "source_table": "orders",
      "target_table": "order_analytics",
      "depth": 1
    }
  ]
}
```

#### GET /lineage-graph

Get the complete lineage graph (all nodes and edges).

**Response (200 OK):**
```json
{
  "nodes": [
    {
      "id": 1,
      "name": "customers",
      "schema_name": "public"
    },
    {
      "id": 2,
      "name": "orders",
      "schema_name": "public"
    }
  ],
  "edges": [
    {
      "id": 101,
      "source": "customers",
      "target": "customer_analytics",
      "dag_id": "etl_pipeline",
      "created_at": "2024-01-15T10:30:45.123456"
    }
  ]
}
```

### Column-Level Lineage

#### POST /column-lineage

Create a column-level lineage relationship.

**Request Body:**
```json
{
  "source_table": "orders",
  "source_column": "order_amount",
  "target_table": "order_analytics",
  "target_column": "total_amount",
  "transformation": "SUM(order_amount)",
  "dag_id": "analytics_dag"
}
```

**Response (201 Created):**
```json
{
  "id": 152,
  "source_table": "orders",
  "source_column": "order_amount",
  "target_table": "order_analytics",
  "target_column": "total_amount",
  "transformation": "SUM(order_amount)",
  "transformation_type": "AGGREGATION",
  "created_at": "2024-01-15T10:30:45.123456"
}
```

#### GET /column-upstream/{table_name}/{column_name}

Get upstream column lineage.

**Response (200 OK):**
```json
{
  "table": "customer_analytics",
  "column": "total_spend",
  "direction": "upstream",
  "depth_limit": 10,
  "total_edges": 2,
  "upstream_columns": ["orders.order_amount", "customers.credit_limit"],
  "lineage_chain": [
    {
      "source_table": "orders",
      "source_column": "order_amount",
      "target_table": "customer_analytics",
      "target_column": "total_spend",
      "transformation": "SUM(order_amount)",
      "depth": 1
    }
  ]
}
```

### Search

#### GET /search/tables

Search for tables by name.

**Parameters:**
- `q` (query parameter, required): Search term
- `match_type` (query parameter, optional): "partial" or "exact" (default: "partial")
- `schema_name` (query parameter, optional): Filter by schema
- `limit` (query parameter, optional): Results per page (default: 20, max: 200)
- `offset` (query parameter, optional): Pagination offset (default: 0)

**Response (200 OK):**
```json
{
  "query": "customer",
  "match_type": "partial",
  "total": 3,
  "tables": [
    {
      "id": 1,
      "name": "customers",
      "schema_name": "public"
    },
    {
      "id": 5,
      "name": "customer_analytics",
      "schema_name": "analytics"
    }
  ]
}
```

**Example:**
```bash
curl "http://localhost:8000/search/tables?q=customer&match_type=partial&limit=10"
```

#### GET /search/columns

Search for columns by name.

**Parameters:**
- `q` (query parameter, required): Column name search term
- `table_name` (query parameter, optional): Filter by table
- `limit` (query parameter, optional): Results per page (default: 20)

**Response (200 OK):**
```json
{
  "query": "customer_id",
  "total": 5,
  "columns": [
    {
      "table_name": "customers",
      "column_name": "customer_id",
      "schema_name": "public"
    },
    {
      "table_name": "orders",
      "column_name": "customer_id",
      "schema_name": "public"
    }
  ]
}
```

### Impact Analysis

#### GET /impact/table/{table_name}

Analyze the impact of changes to a table.

**Parameters:**
- `table_name` (path parameter): Table name to analyze
- `max_depth` (query parameter, optional): Maximum traversal depth (default: 10)

**Response (200 OK):**
```json
{
  "table": "customers",
  "affected_tables": ["customer_analytics", "revenue_summary", "daily_reports"],
  "impacted_dags": ["etl_pipeline", "reporting_pipeline"],
  "severity": "HIGH",
  "lineage_chain": [
    {
      "source_table": "customers",
      "target_table": "customer_analytics",
      "depth": 1
    }
  ]
}
```

**Severity Levels:**
- `NONE`: 0 affected tables
- `LOW`: 1-5 affected tables
- `MEDIUM`: 6-15 affected tables
- `HIGH`: 16-30 affected tables
- `CRITICAL`: 31+ affected tables

#### GET /impact/column/{column_name}

Analyze the impact of changes to a column.

**Parameters:**
- `column_name` (path parameter): Column name to analyze
- `table` (query parameter, optional): Scope search to specific table
- `max_depth` (query parameter, optional): Maximum traversal depth (default: 10)

**Response (200 OK):**
```json
{
  "column": "customer_id",
  "table": "customers",
  "affected_downstream": ["customer_analytics", "revenue_summary"],
  "severity": "MEDIUM",
  "transformation_types": ["DIRECT", "AGGREGATION"]
}
```

### DAG Parsing

#### POST /parse-dag

Parse an Airflow DAG file to extract structure and task dependencies.

**Request Body:**
```json
{
  "dag_file_path": "airflow_dags/etl_pipeline_dag.py"
}
```

Or:

```json
{
  "dag_content": "from airflow import DAG\nfrom datetime import datetime\n\nwith DAG('my_dag', start_date=datetime(2024,1,1)) as dag:\n    pass"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "metadata": {
    "dag": "etl_pipeline",
    "tasks": ["extract", "transform", "load"],
    "dependencies": [
      ["extract", "transform"],
      ["transform", "load"]
    ]
  }
}
```

## Examples

### Example 1: Complete SQL Lineage Flow

```bash
# 1. Parse SQL query
curl -X POST http://localhost:8000/parse-sql \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "INSERT INTO customer_summary SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id;",
    "dialect": "postgres"
  }'

# 2. Create lineage relationship
curl -X POST http://localhost:8000/lineage-relationship \
  -H "Content-Type: application/json" \
  -d '{
    "source_table": "orders",
    "target_table": "customer_summary",
    "dag_id": "daily_etl"
  }'

# 3. Get complete lineage graph
curl http://localhost:8000/lineage-graph

# 4. Analyze downstream impact
curl "http://localhost:8000/impact/table/orders?max_depth=5"
```

### Example 2: Column Lineage Tracking

```bash
# 1. Create column lineage
curl -X POST http://localhost:8000/column-lineage \
  -H "Content-Type: application/json" \
  -d '{
    "source_table": "customers",
    "source_column": "email",
    "target_table": "customer_analytics",
    "target_column": "customer_email",
    "transformation": "UPPER(email)"
  }'

# 2. Trace upstream column lineage
curl "http://localhost:8000/column-upstream/customer_analytics/customer_email?max_depth=5"

# 3. Analyze column-level impact
curl "http://localhost:8000/impact/column/email?table=customers"
```

### Example 3: Metadata Search

```bash
# Search for all customer-related tables
curl "http://localhost:8000/search/tables?q=customer&match_type=partial"

# Search for columns in specific table
curl "http://localhost:8000/search/columns?q=id&table_name=customers"

# Exact table name search
curl "http://localhost:8000/search/tables?q=customers&match_type=exact"
```

## Rate Limiting

Currently, there is no rate limiting on the API. Future versions will implement:
- Per-IP rate limits (1000 requests/hour)
- Per-API-key rate limits (configurable)
- Burst allowances for specific endpoints

## Response Headers

All responses include:

```
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

The `X-Request-ID` header can be used to track requests through logs.

## Pagination

Endpoints that return lists support pagination:

```
?limit=20&offset=0
```

Response includes:

```json
{
  "total": 150,
  "limit": 20,
  "offset": 0,
  "results": [...]
}
```

## API Versioning

Current API version: **2.3.0**

The version is included in:
- HTTP response bodies
- Health check endpoint
- Swagger documentation
- API root endpoint

## Support

For issues or questions:
1. Check the [Testing Guide](./TESTING.md)
2. Review the [README](./README.md)
3. Check application logs in `logs/` directory
4. Open an issue on GitHub

---

**Last Updated:** 2024-01-15  
**API Version:** 2.3.0  
**Status:** Production Ready
