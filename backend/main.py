import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.column_lineage import router as column_lineage_router
from backend.api.dag_lineage import router as dag_lineage_router
from backend.api.impact import router as impact_router
from backend.api.lineage import router as lineage_router
from backend.api.metadata import router as metadata_router
from backend.api.search import router as search_router
from backend.database.db import Base, engine
from backend.logging_config import setup_logging, get_logger, PerformanceLogger
from backend.exceptions import LineageError
from backend.models.error_models import ErrorResponse, ErrorCode, ErrorSeverity
from datetime import datetime

# Ensure ORM models are registered with Base before create_all
import backend.database.orm_models  # noqa: F401

# Initialize structured logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Enterprise Data Lineage Platform",
    description=(
        "REST API for SQL and Airflow DAG lineage extraction. "
        "Parse SQL queries and Airflow DAG files to trace data flow "
        "from source tables through transformations to target tables. "
        "All parsed metadata is persisted to PostgreSQL for unified querying.\n\n"
        "**Week 2 Day 1 additions**\n"
        "- `POST /lineage-relationship` – store a validated lineage edge\n"
        "- `GET /upstream/{table_name}` – recursive upstream lineage (WITH RECURSIVE)\n"
        "- `GET /downstream/{table_name}` – recursive downstream lineage\n"
        "- `GET /lineage-graph` – full dependency graph (nodes + edges)\n"
        "- Circular dependency protection on every new edge write\n\n"
        "**Column Lineage additions**\n"
        "- `POST /column/parse-sql` – parse SQL and save column-level edges with transformation types\n"
        "- `GET /column/upstream/{column_name}` – recursive cross-table column upstream\n"
        "- `GET /column/downstream/{column_name}` – recursive cross-table column downstream\n"
        "- `GET /column/transformations` – transformation type distribution summary\n\n"
        "**Week 2 Day 3 – Impact Analysis**\n"
        "- `GET /impact/table/{table_name}` – downstream blast-radius report for a table change\n"
        "- `GET /impact/column/{column_name}` – downstream blast-radius report for a column change\n"
        "- Severity levels: NONE → LOW → MEDIUM → HIGH → CRITICAL\n"
        "- PostgreSQL WITH RECURSIVE CTEs + circular-dependency guards\n"
        "- Optional `?table=` param on the column endpoint for scoped vs. global search"
    ),
    version="2.3.0",
)


# ============================================================
# Exception Handlers
# ============================================================

@app.exception_handler(LineageError)
async def lineage_error_handler(request: Request, exc: LineageError):
    """Handle custom LineageError exceptions."""
    request_id = request.headers.get("x-request-id", str(uuid4()))
    logger.error(
        f"LineageError: {exc.error_code.value}",
        exc_info=exc,
        extra={
            "request_id": request_id,
            "error_code": exc.error_code.value,
            "severity": exc.severity.value,
        }
    )
    
    response = ErrorResponse(
        success=False,
        error_code=exc.error_code,
        error_message=exc.message,
        severity=exc.severity,
        request_id=request_id,
        timestamp=datetime.utcnow().isoformat(),
    )
    
    # Map severity to HTTP status code
    status_code_map = {
        ErrorSeverity.LOW: 400,
        ErrorSeverity.MEDIUM: 422,
        ErrorSeverity.HIGH: 500,
        ErrorSeverity.CRITICAL: 500,
    }
    
    return JSONResponse(
        status_code=status_code_map.get(exc.severity, 400),
        content=response.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with structured response."""
    request_id = request.headers.get("x-request-id", str(uuid4()))
    
    details = []
    for error in exc.errors():
        details.append({
            "field": ".".join(str(x) for x in error["loc"][1:]) if len(error["loc"]) > 1 else error["loc"][0],
            "message": error["msg"],
            "value": error.get("input"),
        })
    
    response = ErrorResponse(
        success=False,
        error_code=ErrorCode.INVALID_INPUT,
        error_message="Validation error in request body",
        severity=ErrorSeverity.LOW,
        details=details,
        request_id=request_id,
        timestamp=datetime.utcnow().isoformat(),
    )
    
    logger.warning(
        "Validation error",
        extra={
            "request_id": request_id,
            "error_count": len(details),
            "path": request.url.path,
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle Starlette HTTP exceptions with structured response."""
    request_id = request.headers.get("x-request-id", str(uuid4()))
    
    error_code_map = {
        404: ErrorCode.TABLE_NOT_FOUND,
        422: ErrorCode.INVALID_INPUT,
        500: ErrorCode.INTERNAL_SERVER_ERROR,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
    }
    
    error_code = error_code_map.get(exc.status_code, ErrorCode.INTERNAL_SERVER_ERROR)
    severity_map = {
        400: ErrorSeverity.LOW,
        422: ErrorSeverity.LOW,
        404: ErrorSeverity.MEDIUM,
        500: ErrorSeverity.HIGH,
    }
    severity = severity_map.get(exc.status_code, ErrorSeverity.MEDIUM)
    
    response = ErrorResponse(
        success=False,
        error_code=error_code,
        error_message=exc.detail,
        severity=severity,
        request_id=request_id,
        timestamp=datetime.utcnow().isoformat(),
    )
    
    logger.warning(
        f"HTTP Exception: {exc.status_code}",
        extra={"request_id": request_id, "path": request.url.path}
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    request_id = request.headers.get("x-request-id", str(uuid4()))
    
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        extra={"request_id": request_id, "path": request.url.path}
    )
    
    response = ErrorResponse(
        success=False,
        error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        error_message="An unexpected error occurred. Please contact support.",
        severity=ErrorSeverity.CRITICAL,
        request_id=request_id,
        timestamp=datetime.utcnow().isoformat(),
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(),
    )


# ============================================================
# Request ID Middleware
# ============================================================

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to response headers for tracing."""
    request_id = request.headers.get("x-request-id", str(uuid4()))
    request.state.request_id = request_id
    
    with PerformanceLogger(logger, f"{request.method} {request.url.path}", threshold_ms=1000):
        response = await call_next(request)
    
    response.headers["x-request-id"] = request_id
    return response


# ============================================================
# Route Registration
# ============================================================

app.include_router(lineage_router)
app.include_router(dag_lineage_router)
app.include_router(metadata_router)
app.include_router(search_router)
app.include_router(column_lineage_router)
app.include_router(impact_router)


# ============================================================
# Lifecycle Events
# ============================================================

@app.on_event("startup")
def create_tables():
    """Create all ORM-mapped tables in PostgreSQL if they do not exist."""
    logger.info("Creating database tables if not present …")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")


# ============================================================
# Health Check Endpoints
# ============================================================

@app.get("/", tags=["Health"])
def home():
    """Root endpoint providing basic service information."""
    return {
        "message": "Enterprise Data Lineage Platform Running",
        "version": "2.3.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.3.0",
    }


