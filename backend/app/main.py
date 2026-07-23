
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database connected successfully!")
    except Exception as e:
        print(f"Database connection failed: {e}")

    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "running",
    }
