from fastapi import APIRouter

from app.api.v1.endpoints import connections, health, transactions

router = APIRouter()
router.include_router(health.router)
router.include_router(connections.router)
router.include_router(transactions.router)
