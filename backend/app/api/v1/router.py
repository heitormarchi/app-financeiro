from fastapi import APIRouter, Depends

from app.api.v1.endpoints import health, imports
from app.core.auth import require_api_key

router = APIRouter()
router.include_router(health.router, tags=["health"])

protected = APIRouter(dependencies=[Depends(require_api_key)])


@protected.get("/transactions")
async def list_transactions_stub():
    return []


protected.include_router(imports.router, tags=["imports"])

# Tasks seguintes adicionam: ingest, nfce, dashboard, pendencias, push, sources
router.include_router(protected)
