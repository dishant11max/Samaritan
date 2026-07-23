from fastapi import FastAPI

app = FastAPI(
    title="Samaritan API",
    version="0.1.0",
    description="AI-powered cybersecurity platform"
)


@app.get("/")
async def root():
    return {
        "project": "Samaritan",
        "status": "running"
    }
