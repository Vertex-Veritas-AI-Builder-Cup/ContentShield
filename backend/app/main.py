from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_cors_origins
from app.routes.clips import router as clips_router
from app.routes.scan import router as scan_router
from app.routes.verdict_explanation import router as verdict_explanation_router

app = FastAPI(
    title="ContentShield API",
    description="Real-time video content similarity detection",
    version="0.1.0",
)

app.include_router(clips_router)
app.include_router(scan_router)
app.include_router(verdict_explanation_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Return a lightweight liveness response for the API service."""

    return {
        "status": "ok",
        "service": "contentshield-api",
        "version": "0.1.0",
    }


@app.get("/")
def root():
    """Return the API landing-page links used by local development."""

    return {
        "message": "ContentShield API",
        "docs": "/docs",
        "health": "/health",
    }
