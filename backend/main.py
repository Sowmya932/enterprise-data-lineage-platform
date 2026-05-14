from fastapi import FastAPI

app = FastAPI(title="Enterprise Data Lineage Platform")

@app.get("/")
def home():
    return {"message": "Lineage Platform Running"}
