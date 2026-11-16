from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .nlp.pipeline import Analyzer
from .routers import analyze, export, health, pdf_import
from .version import __version__

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    analyzer = Analyzer(settings, use_remote=settings.lt_enabled)
    await analyzer.startup()
    app.state.analyzer = analyzer
    try:
        yield
    finally:
        await analyzer.close()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(export.router)
app.include_router(pdf_import.router)

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
