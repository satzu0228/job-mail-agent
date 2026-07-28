from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.classification.agent import ClassificationAgent
from app.agents.classification.schemas import ClassificationOutput
from app.agents.extraction.agent import ExtractionAgent
from app.agents.extraction.schemas import ExtractionOutput
from app.application.email_analysis import SingleEmailAnalysisService
from app.application.schemas import EmailAnalyzeResponse
from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_db_session
from app.infrastructure.llm import create_chat_model

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def analysis_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> SingleEmailAnalysisService:
    model = create_chat_model(settings)
    return SingleEmailAnalysisService.from_agents(
        session,
        settings.demo_user_id,
        ClassificationAgent.from_model(model),
        ExtractionAgent.from_model(model),
    )


AnalysisServiceDependency = Annotated[
    SingleEmailAnalysisService,
    Depends(analysis_service),
]


@router.post(
    "/emails/{email_id}/classify",
    response_model=ClassificationOutput,
    tags=["email-analysis"],
)
def classify_email(
    email_id: int,
    use_case: AnalysisServiceDependency,
) -> ClassificationOutput:
    return use_case.classify(email_id)


@router.post(
    "/emails/{email_id}/extract",
    response_model=ExtractionOutput,
    tags=["email-analysis"],
)
def extract_email(
    email_id: int,
    use_case: AnalysisServiceDependency,
) -> ExtractionOutput:
    return use_case.extract(email_id)


@router.post(
    "/emails/{email_id}/analyze",
    response_model=EmailAnalyzeResponse,
    tags=["email-analysis"],
)
def analyze_email(
    email_id: int,
    use_case: AnalysisServiceDependency,
) -> EmailAnalyzeResponse:
    result = use_case.analyze(email_id)
    return EmailAnalyzeResponse(
        analysis_id=result.analysis.id,
        email_id=result.analysis.email_id,
        version=result.analysis.version,
        status=result.analysis.status,
        is_current=result.analysis.is_current,
        created_at=result.analysis.created_at,
        classification=result.classification,
        extraction=result.extraction,
    )
