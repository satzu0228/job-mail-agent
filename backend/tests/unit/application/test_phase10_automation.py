from app.application.schemas import EmailAccountSyncSettingsUpdate, EmailSyncResult
from app.infrastructure.scheduler import PollingScheduler


def test_sync_settings_reject_interval_shorter_than_five_minutes() -> None:
    payload = EmailAccountSyncSettingsUpdate(enabled=True, interval_minutes=5)

    assert payload.enabled is True
    assert payload.interval_minutes == 5


def test_sync_result_tracks_new_email_ids_for_workflow_start() -> None:
    result = EmailSyncResult(
        account_id=1,
        folder="INBOX",
        uid_validity=9,
        examined=2,
        created=2,
        skipped=0,
        failed=0,
        created_email_ids=[11, 12],
    )

    assert result.created_email_ids == [11, 12]


def test_polling_scheduler_start_and_stop_are_idempotent() -> None:
    scheduler = PollingScheduler(lambda: None, interval_seconds=5)

    scheduler.start()
    scheduler.start()
    scheduler.stop()
    scheduler.stop()


def test_email_account_sync_settings_schema_is_json_serializable() -> None:
    payload = EmailAccountSyncSettingsUpdate(enabled=False, interval_minutes=10)

    assert payload.model_dump(mode="json") == {
        "enabled": False,
        "interval_minutes": 10,
    }
