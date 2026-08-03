from fastapi import APIRouter

from app.api.v1.endpoints import (
    analysis,
    application_management,
    business,
    dashboard,
    health,
    llm_config,
    reply,
    workflow,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(dashboard.router)
api_router.include_router(business.router)
api_router.include_router(analysis.router)
api_router.include_router(application_management.router)
api_router.include_router(workflow.router)
api_router.include_router(reply.router)
api_router.include_router(llm_config.router)
