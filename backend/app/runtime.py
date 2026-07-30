from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.v1.endpoints.workflow import _workflow_service
from app.application.automation import AutomationService
from app.application.email_access import EmailAccessService
from app.core.config import Settings
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.scheduler import PollingScheduler


def create_automation_scheduler(settings: Settings) -> PollingScheduler:
    def email_access_factory(session: Session) -> EmailAccessService:
        return EmailAccessService(
            session,
            settings.demo_user_id,
            timeout_seconds=settings.email_connect_timeout_seconds,
            default_sync_limit=settings.email_sync_limit,
            max_message_bytes=settings.email_max_message_bytes,
        )

    def start_workflow(email_id: int) -> object:
        with SessionLocal() as session:
            with _workflow_service(session, settings) as service:
                return service.start(email_id)

    service = AutomationService(
        SessionLocal,
        settings.demo_user_id,
        email_access_factory,
        start_workflow,
        reminder_lead_minutes=settings.reminder_lead_minutes,
    )
    return PollingScheduler(
        service.run_cycle,
        interval_seconds=settings.automation_poll_seconds,
    )
