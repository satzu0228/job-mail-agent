from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, sessionmaker

from app.agents.application.agent import ApplicationAgent
from app.agents.classification.agent import ClassificationAgent
from app.agents.extraction.agent import ExtractionAgent
from app.agents.reply import ReplyAgent
from app.application.application_management import ReviewTaskService
from app.application.schemas import (
    ReviewDecision,
    ReviewDecisionResponse,
    WorkflowRunRead,
)
from app.application.workflow import (
    DatabaseWorkflowOperations,
    JobMailWorkflowService,
)
from app.core.config import BACKEND_DIR, Settings, get_settings
from app.infrastructure.checkpoint import sqlite_checkpointer
from app.infrastructure.db.models.workflow_run import WorkflowRun
from app.infrastructure.db.session import get_db_session
from app.infrastructure.llm import create_chat_model
from app.workflows import GRAPH_VERSION

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def _session_factory(session: Session) -> sessionmaker[Session]:
    return sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def _workflow_service(
    session: Session,
    settings: Settings,
) -> Generator[JobMailWorkflowService, None, None]:
    factory = _session_factory(session)
    model = create_chat_model(settings)
    classification = ClassificationAgent.from_model(model)
    extraction = ExtractionAgent.from_model(model)
    application = ApplicationAgent.from_model(model)
    reply = ReplyAgent.from_model(model)
    path = settings.checkpoint_path
    if not path.is_absolute():
        path = BACKEND_DIR / path
    with sqlite_checkpointer(path, settings.checkpoint_encryption_key) as checkpointer:
        operations = DatabaseWorkflowOperations(
            factory,
            settings.demo_user_id,
            classification,
            extraction,
            application,
            reply,
            model_provider=settings.llm_provider,
            model_name=settings.llm_model,
        )
        yield JobMailWorkflowService(
            factory,
            settings.demo_user_id,
            operations,
            checkpointer,
            model_provider=settings.llm_provider,
            model_name=settings.llm_model,
            prompt_versions={
                "classification": classification.prompt_version,
                "extraction": extraction.prompt_version,
                "application": application.prompt_version,
                "reply": reply.prompt_version,
            },
        )


def workflow_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> Generator[JobMailWorkflowService, None, None]:
    with _workflow_service(session, settings) as service:
        yield service


WorkflowDependency = Annotated[
    JobMailWorkflowService,
    Depends(workflow_service),
]


@router.post(
    "/emails/{email_id}/workflow-runs",
    response_model=WorkflowRunRead,
    tags=["workflows"],
)
def start_workflow(
    email_id: int,
    use_case: WorkflowDependency,
) -> WorkflowRunRead:
    return use_case.start(email_id)


@router.get(
    "/workflow-runs/{workflow_run_id}",
    response_model=WorkflowRunRead,
    tags=["workflows"],
)
def get_workflow(
    workflow_run_id: str,
    session: SessionDependency,
    settings: SettingsDependency,
) -> WorkflowRunRead:
    workflow = session.get(WorkflowRun, workflow_run_id)
    if workflow is None or workflow.user_id != settings.demo_user_id:
        from app.infrastructure.db.repositories import EntityNotFoundError

        raise EntityNotFoundError(
            f"Workflow run {workflow_run_id} does not exist"
        )
    return WorkflowRunRead.model_validate(workflow)


class ReviewDecisionCoordinator:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def decide(
        self,
        task_id: str,
        payload: ReviewDecision,
    ) -> ReviewDecisionResponse:
        task = ReviewTaskService(
            self._session,
            self._settings.demo_user_id,
        ).get(task_id)
        workflow = self._session.get(WorkflowRun, task.workflow_run_id)
        is_phase_seven = (
            workflow is not None and workflow.graph_version == GRAPH_VERSION
        )
        self._session.rollback()
        if not is_phase_seven:
            return ReviewTaskService(
                self._session,
                self._settings.demo_user_id,
            ).decide(task_id, payload)
        with _workflow_service(self._session, self._settings) as service:
            return service.decide_review(task_id, payload)


def review_decision_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReviewDecisionCoordinator:
    return ReviewDecisionCoordinator(session, settings)
