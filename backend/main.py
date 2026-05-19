from fastapi import FastAPI
from backend.api.lineage import router as lineage_router
from backend.api.dag_lineage import router as dag_lineage_router

app = FastAPI(
    title="Enterprise Data Lineage Platform",
    description=(
        "REST API for SQL and Airflow DAG lineage extraction. "
        "Parse SQL queries and Airflow DAG files to trace data flow "
        "from source tables through transformations to target tables."
    ),
    version="1.0.0",
)

app.include_router(lineage_router)
app.include_router(dag_lineage_router)


@app.get("/", tags=["Health"])
def home():
    return {"message": "Lineage Platform Running"}

