from fastapi import FastAPI
from backend.api.lineage import router as lineage_router

app = FastAPI(title="Enterprise Data Lineage Platform")

app.include_router(lineage_router)


@app.get("/")
def home():
    return {"message": "Lineage Platform Running"}
