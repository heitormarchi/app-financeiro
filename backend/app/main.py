import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router as api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.services.weekly_service import run_weekly_job


async def _run_weekly_job_scheduled():
    async with AsyncSessionLocal() as session:
        await run_weekly_job(session)


async def _run_inter_sync_scheduled():
    if not settings.inter_client_id:
        return
    from app.services.inter_service import sync_inter
    try:
        async with AsyncSessionLocal() as session:
            await sync_inter(session)
    except Exception:
        logging.exception("sync_inter falhou — fonte fica degradada até o próximo job")


async def _run_projection_job_scheduled():
    from app.services.projection_service import run_projection_job
    try:
        async with AsyncSessionLocal() as session:
            await run_projection_job(session)
    except Exception:
        logging.exception("run_projection_job falhou")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(_run_weekly_job_scheduled, CronTrigger(day_of_week="sun", hour=18, minute=0))
    scheduler.add_job(_run_inter_sync_scheduled, CronTrigger(hour=7, minute=0))
    scheduler.add_job(_run_projection_job_scheduled, CronTrigger(hour=7, minute=30))
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="App Financeiro API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringir em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)

DIST_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "frontend" / "dist",
    Path(__file__).resolve().parents[1] / "frontend" / "dist",
]
DIST = next((p for p in DIST_CANDIDATES if p.exists()), None)

if DIST is not None:
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="spa-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str, request: Request):
        candidate = DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
