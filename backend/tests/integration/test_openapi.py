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
        "/api/v1/emails",
        "/api/v1/emails/{email_id}",
        "/api/v1/job-applications",
        "/api/v1/job-applications/{application_id}",
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/reply-drafts",
        "/api/v1/reply-drafts/{draft_id}",
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
    assert not any("send" in path for path in paths)
    account_read = components["EmailAccountRead"]["properties"]
    assert "credential_ref" not in account_read
    assert "email_address" not in account_read
    assert "email_address_masked" in account_read
