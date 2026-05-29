# Enterprise Data Lineage Platform

## 📋 Overview

A production-ready Python FastAPI-based data lineage platform that:
- **Parses SQL queries** to extract table and column-level lineage
- **Tracks Airflow DAG dependencies** for orchestration visibility
- **Recursively traverses lineage** upstream and downstream
- **Analyzes data change impact** across the organization
- **Provides comprehensive REST APIs** for integration
- **Maintains PostgreSQL persistence** for all metadata
- **Includes enterprise-grade error handling and logging**

## ✨ Features

### Core Capabilities
- ✅ SQL parsing (postgres, mysql, snowflake, bigquery, oracle, etc.)
- ✅ Table-level lineage extraction
- ✅ Column-level lineage with transformation tracking
- ✅ DAG parsing and task dependency extraction
- ✅ Recursive upstream/downstream lineage traversal
- ✅ Impact analysis (blast radius calculation)
- ✅ Circular dependency detection
- ✅ Full lineage graph visualization support

### Backend Stabilization (v2.3.0)
- ✅ Comprehensive Pydantic models for request/response validation
- ✅ Structured error handling with standardized error responses
- ✅ Custom exception hierarchy for different failure scenarios
- ✅ Structured JSON logging across all components
- ✅ Request ID correlation for distributed tracing
- ✅ Performance monitoring and slow operation alerts
- ✅ Comprehensive input validation and sanitization

### Testing & Quality
- ✅ 100+ unit tests (SQL parsing, column lineage, DAG parsing)
- ✅ 50+ integration tests (all API endpoints)
- ✅ Test fixtures and sample data
- ✅ pytest configuration with markers
- ✅ Code coverage reporting
- ✅ Performance benchmarks

### Documentation
- ✅ Complete API documentation with examples
- ✅ Comprehensive testing guide
- ✅ Swagger/OpenAPI documentation
- ✅ Inline code documentation

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 12+
- Git

### Installation

1. **Clone repository:**
```bash
git clone <repo-url>
cd enterprise-data-lineage-platform
```

2. **Create Python environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure database:**
```bash
# Create .env file
cp .env.example .env

# Edit .env with your PostgreSQL connection
DATABASE_URL=postgresql://user:password@localhost:5432/lineage_db
LOG_LEVEL=INFO
```

5. **Initialize database:**
```bash
python setup_database.sql  # Or run directly in PostgreSQL
```

6. **Start the API server:**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

7. **Access Swagger UI:**
- Open http://localhost:8000/docs in your browser

## 📁 Project Structure

```
enterprise-data-lineage-platform/
├── backend/
│   ├── main.py                          # FastAPI app with error handlers
│   ├── exceptions.py                    # Custom exception classes
│   ├── validators.py                    # Input validation utilities
│   ├── logging_config.py                # Structured logging setup
│   ├── api/                             # API route handlers
│   │   ├── lineage.py                   # SQL lineage endpoints
│   │   ├── column_lineage.py            # Column lineage endpoints
│   │   ├── impact.py                    # Impact analysis endpoints
│   │   ├── search.py                    # Search endpoints
│   │   ├── metadata.py                  # Metadata endpoints
│   │   └── dag_lineage.py               # DAG lineage endpoints
│   ├── database/
│   │   ├── db.py                        # Database connection
│   │   └── orm_models.py                # SQLAlchemy models
│   ├── models/
│   │   ├── lineage_models.py            # Pydantic request/response models
│   │   ├── search_models.py             # Search models
│   │   └── error_models.py              # Error response models
│   ├── parsers/
│   │   ├── sql_parser.py                # SQL parsing logic
│   │   └── dag_parser.py                # DAG parsing logic
│   ├── services/
│   │   ├── lineage_service.py           # Lineage business logic
│   │   ├── search_service.py            # Search business logic
│   │   └── dag_service.py               # DAG business logic
│   ├── lineage/
│   │   ├── graph_service.py             # Graph traversal logic
│   │   ├── column_service.py            # Column lineage logic
│   │   └── metadata_service.py          # Metadata logic
│   └── impact_analysis/
│       └── impact_service.py            # Impact analysis logic
├── tests/
│   ├── conftest.py                      # pytest fixtures and configuration
│   ├── test_sql_parser.py               # SQL parsing tests
│   ├── test_column_lineage.py           # Column lineage tests
│   ├── test_dag_parsing.py              # DAG parsing tests
│   ├── test_impact_analysis.py          # Impact analysis tests
│   └── test_api_integration.py          # API integration tests
├── airflow_dags/
│   ├── etl_pipeline_dag.py              # Example ETL DAG
│   ├── reporting_pipeline_dag.py        # Example reporting DAG
│   └── warehouse_loading_dag.py         # Example warehouse DAG
├── sample_data/
│   └── sql/                             # Sample SQL for testing
│       ├── joins.sql
│       ├── aggregations.sql
│       └── nested_queries.sql
├── logs/                                # Application logs
│   ├── application.log
│   ├── error.log
│   └── pytest.log
├── requirements.txt                     # Python dependencies
├── pytest.ini                           # pytest configuration
├── .env.example                         # Environment variables template
├── README.md                            # This file
├── TESTING.md                           # Testing guide
├── API_DOCUMENTATION.md                 # API reference
└── docker-compose.yml                   # Docker setup (optional)
```

## 🔌 API Usage

### Health Check
```bash
curl http://localhost:8000/health
```

### Parse SQL
```bash
curl -X POST http://localhost:8000/parse-sql \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM customers JOIN orders ON customers.id = orders.customer_id;",
    "dialect": "postgres"
  }'
```

### Create Lineage Relationship
```bash
curl -X POST http://localhost:8000/lineage-relationship \
  -H "Content-Type: application/json" \
  -d '{
    "source_table": "customers",
    "target_table": "customer_analytics",
    "dag_id": "etl_pipeline"
  }'
```

### Get Upstream Lineage
```bash
curl http://localhost:8000/upstream/customer_analytics?max_depth=10
```

### Get Impact Analysis
```bash
curl http://localhost:8000/impact/table/customers?max_depth=10
```

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for complete API reference.

## 🧪 Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test Category
```bash
pytest -m unit                          # Unit tests only
pytest -m integration                   # Integration tests
pytest -m db                            # Database tests
pytest -m sql_parser                    # SQL parsing tests
```

### Generate Coverage Report
```bash
pytest --cov=backend --cov-report=html
open htmlcov/index.html
```

### Run with Verbose Output
```bash
pytest -v tests/
pytest -vv --tb=long tests/            # Extra verbose with full tracebacks
```

See [TESTING.md](./TESTING.md) for comprehensive testing guide.

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/lineage_db

# Logging
LOG_LEVEL=INFO                          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOGS_DIR=logs

# Server
HOST=0.0.0.0
PORT=8000
```

### Logging Configuration

The application uses structured JSON logging:

```python
from backend.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Processing started", extra={"user_id": 123})
```

Logs are written to:
- `logs/application.log` - All logs
- `logs/error.log` - Errors only
- `logs/<module>.log` - Module-specific logs

## 📊 Error Handling

All API errors follow a standardized format:

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

Error codes include: `INVALID_TABLE_NAME`, `SQL_PARSE_ERROR`, `DATABASE_ERROR`, `CIRCULAR_DEPENDENCY_DETECTED`, etc.

## 📈 Performance

- SQL parsing: <100ms for typical queries
- DAG parsing: <50ms for small-medium DAGs
- Recursive traversal: <500ms for lineage depth 10 with 100+ tables
- Database queries: <200ms with proper indexing

### Optimization Tips
- Use indexed queries for large lineage graphs
- Set appropriate `max_depth` limits (10-20 recommended)
- Enable query caching for frequent searches
- Monitor slow queries in `logs/error.log`

## 🏢 Enterprise Features

### Request Tracking
Every request gets a unique ID for distributed tracing:
```
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

### Structured Logging
All logs include context:
```json
{
  "timestamp": "2024-01-15T10:30:45",
  "level": "INFO",
  "logger": "backend.api.lineage",
  "message": "Processing SQL query",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "elapsed_ms": 45.23
}
```

### Performance Monitoring
Slow operations are automatically logged:
```
WARN: Slow operation: 'GET /upstream/table_name' took 1523.45ms (threshold: 1000ms)
```

## 🚢 Deployment

### Docker Deployment
```bash
docker-compose up -d
```

### Kubernetes Deployment
```bash
# Configure deployment YAML with your settings
kubectl apply -f deployment.yaml
```

### Production Checklist
- [ ] Set `DEBUG=false`
- [ ] Configure production database
- [ ] Set strong `SECRET_KEY`
- [ ] Enable HTTPS
- [ ] Configure logging aggregation
- [ ] Set up monitoring and alerting
- [ ] Enable rate limiting
- [ ] Configure CORS properly
- [ ] Run security scan: `bandit backend/`
- [ ] Run linting: `flake8 backend/`

## 📚 Documentation

- **[API Documentation](./API_DOCUMENTATION.md)** - Complete API reference with examples
- **[Testing Guide](./TESTING.md)** - Testing strategy and best practices
- **[README.md](./README.md)** - This file
- **Swagger UI** - Interactive API documentation at http://localhost:8000/docs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Submit a pull request

### Code Style
- Follow PEP 8
- Use type hints
- Add docstrings to functions
- Run `black` for formatting: `black backend/`

### Before Submitting PR
```bash
pytest                              # All tests pass
pytest --cov=backend               # Coverage >80%
flake8 backend/                     # No linting errors
black --check backend/              # Code formatted
mypy backend/                       # No type errors
```

## 🐛 Troubleshooting

### Issue: Database connection refused
```
Error: could not connect to server: Connection refused
```
**Solution:** Ensure PostgreSQL is running:
```bash
postgres -D /usr/local/var/postgres
```

### Issue: Tests fail with "Cannot find module backend"
**Solution:** Run tests from repository root:
```bash
cd enterprise-data-lineage-platform
pytest
```

### Issue: "Circular dependency detected" error
**Solution:** This is expected if your lineage contains cycles. The system detects and reports them. Review your data sources.

### Issue: Slow queries
**Solution:** 
1. Add database indexes on frequently queried columns
2. Reduce `max_depth` parameter
3. Check logs for slow query warnings
4. Monitor database performance

## 📝 License

This project is licensed under the MIT License - see LICENSE file for details.

## 👥 Team

- **Lead Developer:** [Your Name]
- **Contributors:** [Contributors List]
- **Maintainer:** [Maintainer Email]

## 📞 Support

- **Documentation:** [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
- **Issues:** Report on GitHub
- **Email:** support@example.com

## 🗺️ Roadmap

### Q1 2024
- [ ] API authentication (OAuth 2.0)
- [ ] GraphQL endpoint
- [ ] Real-time lineage updates

### Q2 2024
- [ ] Web UI dashboard
- [ ] Lineage visualization
- [ ] Advanced filtering

### Q3 2024
- [ ] Machine learning-based anomaly detection
- [ ] Custom lineage rules engine
- [ ] Data quality integration

### Q4 2024
- [ ] Advanced caching and performance optimization
- [ ] Multi-tenant support
- [ ] Enterprise integrations

---

**Version:** 2.3.0  
**Last Updated:** 2024-01-15  
**Status:** Production Ready ✅

