from fastapi.testclient import TestClient


def test_swagger_and_third_phase_routes_are_available(client: TestClient) -> None:
    docs_response = client.get("/docs")
    schema_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert schema_response.status_code == 200
    paths = schema_response.json()["paths"]
    expected_paths = {
        "/api/v1/email-accounts",
        "/api/v1/email-accounts/{account_id}/test-connection",
        "/api/v1/email-accounts/{account_id}/sync",
        "/api/v1/email-accounts/{account_id}/active",
        "/api/v1/emails",
        "/api/v1/emails/query",
        "/api/v1/emails/{email_id}",
        "/api/v1/emails/{email_id}/attachments/{attachment_index}",
        "/api/v1/emails/{email_id}/classify",
        "/api/v1/emails/{email_id}/extract",
        "/api/v1/emails/{email_id}/analyze",
        "/api/v1/emails/{email_id}/match-application",
        "/api/v1/job-applications",
        "/api/v1/job-applications/query",
        "/api/v1/job-applications/{application_id}",
        "/api/v1/job-applications/{application_id}/events",
        "/api/v1/review-tasks",
        "/api/v1/review-tasks/query",
        "/api/v1/review-tasks/{task_id}",
        "/api/v1/review-tasks/{task_id}/decision",
        "/api/v1/tasks",
        "/api/v1/tasks/query",
        "/api/v1/tasks/{task_id}",
        "/api/v1/reply-drafts",
        "/api/v1/reply-drafts/{draft_id}",
        "/api/v1/reply-drafts/{draft_id}/send",
        "/api/v1/emails/{email_id}/generate-reply",
    }
    assert expected_paths <= paths.keys()


def test_basic_api_does_not_expose_critical_state_or_send_actions(
    client: TestClient,
) -> None:
    schema = client.get("/openapi.json").json()
    components = schema["components"]["schemas"]

    application_update = components["JobApplicationUpdate"]["properties"]
    draft_update = components["ReplyDraftUpdate"]["properties"]
    paths = schema["paths"]

    assert "current_stage" not in application_update
    assert "status" not in application_update
    assert set(draft_update) == {"reviewed_body"}
    send_paths = {path for path in paths if "send" in path}
    assert send_paths == {"/api/v1/reply-drafts/{draft_id}/send"}
    account_read = components["EmailAccountRead"]["properties"]
    assert "credential_ref" not in account_read
    assert "email_address" in account_read
    assert "email_address_masked" in account_read
