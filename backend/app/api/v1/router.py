from fastapi import APIRouter

from app.api.v1.endpoints import (
    analysis,
    application_management,
    business,
    health,
    workflow,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(business.router)
api_router.include_router(analysis.router)
api_router.include_router(application_management.router)
api_router.include_router(workflow.router)
