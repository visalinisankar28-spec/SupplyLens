"""
Application entrypoint.

Run locally with: uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router

app = FastAPI(
    title="Supply Chain Transparency Platform - Dependency Health Module",
    description="Computes the Dependency Health Index (DHI) for SBOM components "
    "using OpenSSF Scorecard and package registry signals.",
    version="0.2.0",
)

# In production, restrict this to the actual frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["Ops"])
def liveness_check() -> dict[str, str]:
    """Basic liveness probe for container orchestration - not part of the DHI feature."""
    return {"status": "ok"}
