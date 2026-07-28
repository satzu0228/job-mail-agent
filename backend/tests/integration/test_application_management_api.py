from fastapi.testclient import TestClient

from app.agents.application.schemas import (
    ApplicationAgentOutput,
    ApplicationRecommendation,
)
from app.api.v1.endpoints.application_management import management_service
from app.application.schemas import ApplicationMatchResponse
from app.domain.enums import ApplicationStage
from app.main import app


class StubManagementService:
    def match_email(self, email_id: int) -> ApplicationMatchResponse:
        assert email_id == 8
        return ApplicationMatchResponse(
            email_id=email_id,
            analysis_id=15,
            candidates=[],
            suggestion=ApplicationAgentOutput(
                recommendation=ApplicationRecommendation.CREATE_NEW,
                proposed_stage=ApplicationStage.INTERVIEW,
                confidence=0.92,
                reasoning="没有合理候选，建议创建申请并等待用户确认。",
            ),
            review_task_id="d521dbb4-812f-496a-9d95-d889698368a5",
        )


def test_match_application_only_returns_pending_review_suggestion(
    client: TestClient,
) -> None:
    app.dependency_overrides[management_service] = StubManagementService
    try:
        response = client.post("/api/v1/emails/8/match-application")
    finally:
        app.dependency_overrides.pop(management_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion"]["recommendation"] == "CREATE_NEW"
    assert payload["suggestion"]["proposed_stage"] == "INTERVIEW"
    assert payload["requires_human_confirmation"] is True
    assert payload["review_task_id"]
