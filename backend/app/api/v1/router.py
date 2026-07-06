from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (dashboard, health, imports, ingest, inter, nfce, pendencias,
                                   push, recurring, scheduled, sources, transactions, transfers,
                                   webhooks)
from app.core.auth import require_api_key

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(webhooks.router, tags=["webhooks"])  # segurança própria via token+JID

protected = APIRouter(dependencies=[Depends(require_api_key)])

protected.include_router(imports.router, tags=["imports"])
protected.include_router(sources.router, tags=["sources"])
protected.include_router(ingest.router, tags=["ingest"])
protected.include_router(nfce.router, tags=["nfce"])
protected.include_router(dashboard.router, tags=["dashboard"])
protected.include_router(transactions.router, tags=["transactions"])
protected.include_router(pendencias.router, tags=["pendencias"])
protected.include_router(push.router, tags=["push"])
protected.include_router(scheduled.router, tags=["scheduled"])
protected.include_router(recurring.router, tags=["recurring"])
protected.include_router(inter.router, tags=["inter"])
protected.include_router(transfers.router, tags=["transfers"])

router.include_router(protected)
