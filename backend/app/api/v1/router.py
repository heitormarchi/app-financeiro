from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (dashboard, health, imports, ingest, nfce, pendencias,
                                   push, sources, transactions)
from app.core.auth import require_api_key

router = APIRouter()
router.include_router(health.router, tags=["health"])

protected = APIRouter(dependencies=[Depends(require_api_key)])

protected.include_router(imports.router, tags=["imports"])
protected.include_router(sources.router, tags=["sources"])
protected.include_router(ingest.router, tags=["ingest"])
protected.include_router(nfce.router, tags=["nfce"])
protected.include_router(dashboard.router, tags=["dashboard"])
protected.include_router(transactions.router, tags=["transactions"])
protected.include_router(pendencias.router, tags=["pendencias"])
protected.include_router(push.router, tags=["push"])

router.include_router(protected)
