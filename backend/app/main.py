from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.application.application_management import (
    ApplicationAnalysisUnavailableError,
    ApplicationModelExecutionError,
)
from app.application.email_access import EmailSyncError
from app.application.email_analysis import (
    EmailModelExecutionError,
    EmailNotReadyForAnalysisError,
    NonJobEmailExtractionError,
)
from app.application.workflow import WorkflowCheckpointUnavailableError
from app.core.config import get_settings
from app.infrastructure.checkpoint import CheckpointConfigurationError
from app.infrastructure.db.repositories import (
    EntityNotFoundError,
    ResourceConflictError,
    VersionConflictError,
)
from app.infrastructure.llm import LLMConfigurationError


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.exception_handler(EntityNotFoundError)
    def not_found_handler(
        request: Request,
        exc: EntityNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @application.exception_handler(VersionConflictError)
    def version_conflict_handler(
        request: Request,
        exc: VersionConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @application.exception_handler(ResourceConflictError)
    def resource_conflict_handler(
        request: Request,
        exc: ResourceConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @application.exception_handler(EmailSyncError)
    def email_sync_handler(
        request: Request,
        exc: EmailSyncError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": str(exc)},
        )

    @application.exception_handler(EmailNotReadyForAnalysisError)
    @application.exception_handler(NonJobEmailExtractionError)
    def analysis_conflict_handler(
        request: Request,
        exc: EmailNotReadyForAnalysisError | NonJobEmailExtractionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @application.exception_handler(EmailModelExecutionError)
    @application.exception_handler(ApplicationModelExecutionError)
    def model_execution_handler(
        request: Request,
        exc: EmailModelExecutionError | ApplicationModelExecutionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": str(exc)},
        )

    @application.exception_handler(ApplicationAnalysisUnavailableError)
    def application_analysis_conflict_handler(
        request: Request,
        exc: ApplicationAnalysisUnavailableError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @application.exception_handler(LLMConfigurationError)
    @application.exception_handler(CheckpointConfigurationError)
    def model_configuration_handler(
        request: Request,
        exc: LLMConfigurationError | CheckpointConfigurationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(exc)},
        )

    @application.exception_handler(WorkflowCheckpointUnavailableError)
    def checkpoint_unavailable_handler(
        request: Request,
        exc: WorkflowCheckpointUnavailableError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )
    return application


app = create_app()
