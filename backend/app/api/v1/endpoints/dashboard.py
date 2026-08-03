from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.dashboard import DashboardService
from app.application.schemas import (
    DashboardRead,
    DashboardStats,
    ReviewTaskRead,
    TaskRead,
)
from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_db_session

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/dashboard", response_model=DashboardRead, tags=["dashboard"])
def get_dashboard(
    session: SessionDependency,
    settings: SettingsDependency,
) -> DashboardRead:
    data = DashboardService(session, settings.demo_user_id).get_dashboard()

    return DashboardRead(
        upcoming_interviews=[
            TaskRead.model_validate(task) for task in data["upcoming_interviews"]
        ],
        urgent_deadlines=[
            TaskRead.model_validate(task) for task in data["urgent_deadlines"]
        ],
        pending_reviews=[
            ReviewTaskRead.model_validate(task)
            for task in data["pending_reviews"]
        ],
        stats=DashboardStats(**data["stats"]),
    )
