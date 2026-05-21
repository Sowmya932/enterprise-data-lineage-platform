import logging

from fastapi import FastAPI

from backend.api.dag_lineage import router as dag_lineage_router
from backend.api.lineage import router as lineage_router
from backend.api.metadata import router as metadata_router
from backend.database.db import Base, engine

# Ensure ORM models are registered with Base before create_all
import backend.database.orm_models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

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
        "- Circular dependency protection on every new edge write"
    ),
    version="2.1.0",
)

app.include_router(lineage_router)
app.include_router(dag_lineage_router)
app.include_router(metadata_router)


@app.on_event("startup")
def create_tables():
    """Create all ORM-mapped tables in PostgreSQL if they do not exist."""
    logger.info("Creating database tables if not present …")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")


@app.get("/", tags=["Health"])
def home():
    return {"message": "Lineage Platform Running", "docs": "/docs"}

