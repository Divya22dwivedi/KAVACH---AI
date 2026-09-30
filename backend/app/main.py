"""KavachAI FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .routers import (
    attacks,
    datasets,
    demo,
    evaluation,
    findings,
    inference,
    models,
    provenance,
    reports,
    scans,
    shift,
)
from .schemas import Health


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="KavachAI API",
    description=(
        "Offline AI-assurance workbench for SIH 2026 (SIH26228). "
        "Evidence-backed integrity verdicts for CV data, models and "
        "inference provenance. No network calls at runtime."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Dev-only CORS for the local Vite frontend. Never open this in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(scans.router)
app.include_router(models.router)
app.include_router(inference.router)
app.include_router(provenance.router)
app.include_router(shift.router)
app.include_router(findings.router)
app.include_router(reports.router)
app.include_router(attacks.router)
app.include_router(evaluation.router)
app.include_router(demo.router)


@app.get("/api/v1/health", response_model=Health, tags=["health"])
def health() -> Health:
    try:
        con = db.get_connection()
        con.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return Health(db_ok=db_ok)


@app.exception_handler(ValueError)
def _value_error_handler(_, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
              name="frontend-assets")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def frontend_route(frontend_path: str) -> FileResponse:
        if frontend_path == "api" or frontend_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(_FRONTEND_DIST / "index.html")
