from datetime import datetime

from fastapi.testclient import TestClient

from app.api.v1.endpoints.workflow import workflow_service
from app.application.schemas import WorkflowRunRead
from app.domain.enums import WorkflowRunStatus
from app.main import app


class StubWorkflowService:
    def start(self, email_id: int) -> WorkflowRunRead:
        assert email_id == 8
        now = datetime(2026, 7, 29, 8, 0)
        return WorkflowRunRead(
            id="d521dbb4-812f-496a-9d95-d889698368a5",
            thread_id="ba7181bf-475a-40f4-b842-bf0a27503db1",
            user_id=1,
            email_id=email_id,
            status=WorkflowRunStatus.WAITING_REVIEW,
            current_node="human_review",
            graph_version="job-mail-workflow.v1",
            model_provider="stub",
            model_name="stub-model",
            prompt_versions={
                "classification": "v1",
                "extraction": "v1",
                "application": "v1",
            },
            agent_trace=[],
            pending_review_task_id="f034407d-2c22-45fa-9f63-2cdfb2e1576f",
            started_at=now,
            finished_at=None,
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        )


def test_start_workflow_returns_persisted_run_status(client: TestClient) -> None:
    app.dependency_overrides[workflow_service] = StubWorkflowService
    try:
        response = client.post("/api/v1/emails/8/workflow-runs")
    finally:
        app.dependency_overrides.pop(workflow_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "WAITING_REVIEW"
    assert payload["current_node"] == "human_review"
    assert payload["pending_review_task_id"]
