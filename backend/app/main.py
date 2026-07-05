from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.services.weekly_service import run_weekly_job


async def _run_weekly_job_scheduled():
    async with AsyncSessionLocal() as session:
        await run_weekly_job(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(_run_weekly_job_scheduled, CronTrigger(day_of_week="sun", hour=18, minute=0))
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
