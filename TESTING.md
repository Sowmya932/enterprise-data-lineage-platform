# Testing Guide

## Overview

This document provides comprehensive information about testing the Enterprise Data Lineage Platform. The test suite includes unit tests, integration tests, and performance tests covering all major components.

## Test Structure

```
tests/
├── conftest.py                 # Pytest configuration and shared fixtures
├── test_sql_parser.py         # SQL parsing unit tests
├── test_column_lineage.py     # Column lineage unit tests
├── test_dag_parsing.py        # DAG parsing unit tests
├── test_impact_analysis.py    # Impact analysis tests
├── test_api_integration.py    # FastAPI endpoint integration tests
└── __pycache__/
```

## Running Tests

### Prerequisites

Install dependencies:

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

**Unit tests only (fast):**
```bash
pytest -m unit
```

**Integration tests:**
```bash
pytest -m integration
```

**Database tests:**
```bash
pytest -m db
```

**Specific component tests:**
```bash
pytest -m sql_parser        # SQL parsing tests
pytest -m lineage          # Lineage-related tests
pytest -m impact           # Impact analysis tests
pytest -m search           # Search functionality tests
```

### Run Individual Test Files

```bash
pytest tests/test_sql_parser.py
pytest tests/test_api_integration.py
```

### Run Specific Test Class

```bash
pytest tests/test_sql_parser.py::TestSQLParserBasics
```

### Run Specific Test

```bash
pytest tests/test_sql_parser.py::TestSQLParserBasics::test_parse_simple_select
```

### Verbose Output

```bash
pytest -v
pytest -vv  # Extra verbose
```

## Test Configuration

### pytest.ini

Configuration file located at `pytest.ini` defines:
- Test discovery patterns
- Markers (unit, integration, slow, db, etc.)
- Output formatting
- Logging levels
- Timeout settings

### conftest.py

Provides shared fixtures:

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `test_engine` | session | SQLite test database engine |
| `test_db` | function | Fresh database session per test |
| `client` | function | FastAPI test client |
| `sample_tables` | function | Sample table records |
| `sample_lineage_relationships` | function | Sample lineage edges |
| `sample_column_lineage` | function | Sample column-level lineage |
| `sample_sql_queries` | function | Sample SQL for testing |
| `sample_dag_content` | function | Sample Airflow DAG code |

## Test Coverage

### Unit Tests

#### SQL Parser (`test_sql_parser.py`)
- Basic SELECT, INSERT, UPDATE, DELETE parsing
- Complex queries (JOINs, subqueries, CTEs)
- Column lineage extraction
- SQL dialect validation
- Error handling and edge cases

**Coverage:** ~85% of SQL parsing logic

#### Column Lineage (`test_column_lineage.py`)
- Column name validation
- Table name validation
- Column lineage creation and traversal
- Transformation tracking
- Validation rules

**Coverage:** ~80% of column lineage logic

#### DAG Parsing (`test_dag_parsing.py`)
- DAG metadata extraction
- Task dependency parsing
- Complex DAG structures
- Error handling

**Coverage:** ~75% of DAG parsing logic

### Integration Tests

#### API Endpoints (`test_api_integration.py`)
- SQL parsing endpoints
- Lineage relationship CRUD
- Recursive lineage traversal
- Column lineage operations
- Search APIs
- Impact analysis APIs
- Error handling and validation
- Request ID tracking

**Coverage:** All public API endpoints

#### Impact Analysis (`test_impact_analysis.py`)
- Table-level impact analysis
- Column-level impact analysis
- Severity calculations
- Circular dependency handling
- Deep lineage chains
- Performance with large graphs

**Coverage:** ~90% of impact analysis

## Test Markers

Tests are marked for easy filtering:

```python
@pytest.mark.unit              # Fast unit tests
@pytest.mark.integration       # Integration tests
@pytest.mark.slow              # Slow-running tests
@pytest.mark.db                # Tests requiring database
@pytest.mark.sql_parser        # SQL parsing tests
@pytest.mark.lineage           # Lineage tests
@pytest.mark.impact            # Impact analysis tests
@pytest.mark.search            # Search tests
```

## Fixtures in Detail

### Database Fixtures

**test_engine (session-scoped):**
```python
def test_engine():
    """Create a test database engine."""
    # Creates in-memory SQLite database
    # Persists for entire test session
    # Cleaned up after all tests
```

**test_db (function-scoped):**
```python
def test_db(test_session_factory):
    """Provide a fresh test database session for each test."""
    # Fresh transaction for each test
    # Rolls back after test completion
    # Ensures test isolation
```

**client (function-scoped):**
```python
def client(test_db):
    """Provide a FastAPI test client with test database dependency."""
    # Overrides get_db dependency
    # Uses test database for all requests
    # Provides TestClient for making HTTP requests
```

### Data Fixtures

**sample_tables:**
```python
@pytest.fixture
def sample_tables(test_db):
    # Creates: customers, orders, products, order_details, etc.
    # Returns dict mapping table name to TableRecord
```

**sample_lineage_relationships:**
```python
@pytest.fixture
def sample_lineage_relationships(test_db, sample_tables):
    # Creates relationships: customers -> customer_analytics, etc.
    # Returns list of LineageRelationship objects
```

**sample_column_lineage:**
```python
@pytest.fixture
def sample_column_lineage(test_db, sample_tables):
    # Creates column-level edges with transformations
    # Includes DIRECT and AGGREGATION types
```

## Writing Tests

### Basic Unit Test

```python
import pytest

@pytest.mark.unit
def test_parse_simple_select():
    """Test parsing a simple SELECT statement."""
    parser = SQLParser(dialect="postgres")
    sql = "SELECT * FROM customers;"
    result = parser.parse(sql)
    
    assert result["target_table"] is None
    assert "customers" in result["source_tables"]
    assert result["success"] is True
```

### Using Fixtures

```python
@pytest.mark.unit
def test_something_with_fixture(test_db, sample_tables):
    """Test using fixtures."""
    # test_db provides database session
    # sample_tables provides pre-created tables
    
    users = test_db.query(TableRecord).filter_by(name="customers").first()
    assert users is not None
```

### Integration Test with API

```python
@pytest.mark.integration
def test_parse_sql_endpoint(client, sample_sql_queries):
    """Test POST /parse-sql endpoint."""
    response = client.post(
        "/parse-sql",
        json={
            "sql": sample_sql_queries["simple_select"],
            "dialect": "postgres",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
```

### Testing Error Cases

```python
@pytest.mark.unit
def test_invalid_column_name():
    """Test that invalid column names raise errors."""
    with pytest.raises(InvalidColumnNameError):
        validate_column_name("")
```

## Debugging Tests

### Print Debug Output

```python
def test_something():
    result = parser.parse(sql)
    print(f"Debug output: {result}")  # Shows with pytest -s
    assert result
```

### Use pytest -s (no capture)

```bash
pytest -s tests/test_file.py  # Shows print() output
```

### Use pdb Debugger

```python
def test_something():
    import pdb; pdb.set_trace()  # Breakpoint
    result = parser.parse(sql)
```

### Verbose Failure Output

```bash
pytest -vv --tb=long tests/test_file.py
```

## Coverage Reports

Generate coverage reports:

```bash
# Terminal report
pytest --cov=backend --cov-report=term-missing

# HTML report
pytest --cov=backend --cov-report=html

# XML report (for CI/CD)
pytest --cov=backend --cov-report=xml
```

Coverage reports generate in `htmlcov/` directory.

## Performance Testing

### Measure Test Speed

```bash
pytest --durations=10  # Shows slowest 10 tests
```

### Run Only Fast Tests

```bash
pytest -m "not slow"
```

### Run Slow Tests

```bash
pytest -m slow
```

### Timeout Tests

Tests have a 300-second timeout by default (configured in pytest.ini).

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.10
      - run: pip install -r requirements.txt
      - run: pytest --cov=backend
```

## Common Issues and Solutions

### Issue: "Cannot find module backend"

**Solution:** Ensure you're running pytest from workspace root:
```bash
cd enterprise-data-lineage-platform
pytest
```

### Issue: Database locked error

**Solution:** Close other connections and ensure SQLite is in temp directory:
```python
# conftest.py uses ":memory:" by default
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
```

### Issue: Fixture not found

**Solution:** Ensure conftest.py is in tests/ directory and properly formatted.

### Issue: Tests pass locally but fail in CI

**Solution:** 
- Check environment variables (DATABASE_URL, LOG_LEVEL)
- Verify test database isolation
- Check for timing-dependent tests

## Best Practices

1. **Test Isolation:** Each test should be independent
2. **Descriptive Names:** Test names should describe what they test
3. **Arrange-Act-Assert:** Organize tests into these three sections
4. **Fixtures:** Use fixtures for setup/teardown, not test logic
5. **Markers:** Use markers to categorize tests
6. **Error Cases:** Test both happy path and error cases
7. **No Hardcoding:** Use fixtures and parametrization instead
8. **Fast Feedback:** Keep unit tests fast, mark slow tests

## Example: Complete Test

```python
import pytest
from fastapi import status

@pytest.mark.integration
@pytest.mark.db
def test_create_column_lineage(client, test_db):
    """
    Test creating a column lineage relationship via API.
    
    This integration test verifies:
    1. Column lineage can be created through API
    2. Response contains expected fields
    3. Data is persisted to database
    """
    # Arrange
    from backend.database.orm_models import TableRecord
    test_db.add_all([
        TableRecord(name="source", schema_name="public"),
        TableRecord(name="target", schema_name="public"),
    ])
    test_db.commit()
    
    payload = {
        "source_table": "source",
        "source_column": "id",
        "target_table": "target",
        "target_column": "source_id",
        "transformation": "DIRECT",
    }
    
    # Act
    response = client.post("/column-lineage", json=payload)
    
    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["source_table"] == "source"
    assert data["target_column"] == "source_id"
    
    # Verify persistence
    from backend.database.orm_models import ColumnLineage
    col = test_db.query(ColumnLineage).filter_by(
        source_table="source"
    ).first()
    assert col is not None
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/20/faq/testing.html)
- [Pydantic Validation](https://docs.pydantic.dev/)
