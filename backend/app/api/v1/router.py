"""
API V1 Main Router
"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    storage_connections,
    telemetry,
    policy,
    recommendations,
    approval_execution_api,
    dashboard,
    costs,
    benchmark,
    ml_api,
    local_storage_api,
)

api_router = APIRouter()
api_router.include_router(storage_connections.router)
api_router.include_router(telemetry.router)
api_router.include_router(policy.router)
api_router.include_router(recommendations.router)
api_router.include_router(approval_execution_api.router)
api_router.include_router(dashboard.router)
api_router.include_router(costs.router)
api_router.include_router(benchmark.router)
api_router.include_router(ml_api.router)
api_router.include_router(local_storage_api.router)

