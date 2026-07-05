from fastapi import APIRouter, Depends

from app.api.v1.endpoints import health, imports, ingest, sources
from app.core.auth import require_api_key

router = APIRouter()
router.include_router(health.router, tags=["health"])

protected = APIRouter(dependencies=[Depends(require_api_key)])


@protected.get("/transactions")
async def list_transactions_stub():
    return []


protected.include_router(imports.router, tags=["imports"])
protected.include_router(sources.router, tags=["sources"])
protected.include_router(ingest.router, tags=["ingest"])

# Tasks seguintes adicionam: nfce, dashboard, pendencias, push
router.include_router(protected)
