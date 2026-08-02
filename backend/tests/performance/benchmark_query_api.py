"""第十一阶段本地 MySQL 查询 API 基准测试。"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from statistics import quantiles
from time import perf_counter

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    ApplicationStatus,
    ArchiveStatus,
    EmailParseStatus,
    TransportSecurity,
)
from app.infrastructure.db.models import (
    ApplicationEvent,
    Email,
    EmailAccount,
    JobApplication,
    User,
)
from app.infrastructure.db.session import engine
from app.main import app

TEST_USER_ID = 9_110_000_011
EMAIL_COUNT = 1_000
APPLICATION_COUNT = 100
EVENT_COUNT = 1_000


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def seed() -> tuple[int, int]:
    now = _utc_now()
    with Session(engine) as session:
        if session.get(User, TEST_USER_ID) is not None:
            raise RuntimeError("性能测试用户已存在；请先检查上次运行的清理状态")
        user = User(
            id=TEST_USER_ID,
            display_name="Phase 11 performance fixture",
            timezone="Asia/Shanghai",
            reply_preferences={},
        )
        session.add(user)
        session.flush()
        account = EmailAccount(
            user_id=TEST_USER_ID,
            provider="fixture",
            email_address="phase11-performance@example.test",
            imap_host="imap.example.test",
            imap_port=993,
            imap_security=TransportSecurity.SSL,
            smtp_host="smtp.example.test",
            smtp_port=465,
            smtp_security=TransportSecurity.SSL,
            credential_ciphertext="v1:performance-fixture",
            is_active=False,
        )
        session.add(account)
        session.flush()
        applications = [
            JobApplication(
                user_id=TEST_USER_ID,
                company_name=f"脱敏公司 {index:03d}",
                position_name=f"测试岗位 {index:03d}",
                current_stage=ApplicationStage.INTERVIEW,
                status=ApplicationStatus.ACTIVE,
                source=ApplicationSource.EMAIL,
                applied_at=now - timedelta(days=index),
            )
            for index in range(APPLICATION_COUNT)
        ]
        session.add_all(applications)
        session.flush()
        emails = [
            Email(
                account_id=account.id,
                application_id=applications[index % APPLICATION_COUNT].id,
                source_folder="INBOX",
                current_folder="INBOX",
                uid_validity=20260730,
                imap_uid=index + 1,
                message_id=f"<phase11-performance-{index}@example.test>",
                subject=f"第十一阶段性能测试邮件 {index:04d}",
                from_name="脱敏招聘组",
                from_address="recruiter@example.test",
                to_recipients=[{"address": "phase11-performance@example.test"}],
                cc_recipients=[],
                received_at=now - timedelta(minutes=index),
                plain_body="仅用于本地性能测试的脱敏正文。",
                analysis_text="仅用于本地性能测试的脱敏正文。",
                attachment_metadata=[],
                parse_status=EmailParseStatus.SUCCEEDED,
                archive_status=ArchiveStatus.NONE,
            )
            for index in range(EMAIL_COUNT)
        ]
        session.add_all(emails)
        session.flush()
        events = [
            ApplicationEvent(
                application_id=applications[index % APPLICATION_COUNT].id,
                event_type="PERFORMANCE_FIXTURE",
                previous_stage=ApplicationStage.APPLIED,
                proposed_stage=ApplicationStage.INTERVIEW,
                confirmed_stage=ApplicationStage.INTERVIEW,
                raw_time_text="脱敏测试时间",
                event_at=now - timedelta(minutes=index),
                source_timezone="Asia/Shanghai",
            )
            for index in range(EVENT_COUNT)
        ]
        session.add_all(events)
        session.commit()
        return emails[0].id, applications[0].id


def cleanup() -> None:
    with Session(engine) as session:
        account_ids = list(
            session.scalars(
                select(EmailAccount.id).where(EmailAccount.user_id == TEST_USER_ID)
            )
        )
        application_ids = list(
            session.scalars(
                select(JobApplication.id).where(JobApplication.user_id == TEST_USER_ID)
            )
        )
        if account_ids:
            session.execute(delete(Email).where(Email.account_id.in_(account_ids)))
        if application_ids:
            session.execute(
                delete(ApplicationEvent).where(
                    ApplicationEvent.application_id.in_(application_ids)
                )
            )
            session.execute(
                delete(JobApplication).where(JobApplication.id.in_(application_ids))
            )
        session.execute(
            delete(EmailAccount).where(EmailAccount.user_id == TEST_USER_ID)
        )
        session.execute(delete(User).where(User.id == TEST_USER_ID))
        session.commit()


async def _timed_get(client: httpx.AsyncClient, path: str) -> float:
    started = perf_counter()
    response = await client.get(path)
    elapsed_ms = (perf_counter() - started) * 1_000
    response.raise_for_status()
    return elapsed_ms


def _p95(values: list[float]) -> float:
    return quantiles(values, n=100, method="inclusive")[94]


async def benchmark(email_id: int, application_id: int) -> dict[str, object]:
    settings = get_settings().model_copy(
        update={"demo_user_id": TEST_USER_ID, "automation_enabled": False}
    )
    app.dependency_overrides[get_settings] = lambda: settings
    transport = httpx.ASGITransport(app=app)
    endpoints = {
        "emails_query": "/api/v1/emails/query?limit=50",
        "email_detail": f"/api/v1/emails/{email_id}",
        "applications_query": "/api/v1/job-applications/query?limit=50",
        "application_events": (
            f"/api/v1/job-applications/{application_id}/events?limit=50"
        ),
    }
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://phase11.test",
            timeout=30,
        ) as client:
            for path in endpoints.values():
                for _ in range(5):
                    await _timed_get(client, path)
            results: dict[str, object] = {}
            for name, path in endpoints.items():
                samples = [await _timed_get(client, path) for _ in range(40)]
                results[name] = {
                    "requests": len(samples),
                    "p95_ms": round(_p95(samples), 2),
                    "max_ms": round(max(samples), 2),
                }
            concurrent = await asyncio.gather(
                *[
                    _timed_get(client, "/api/v1/emails/query?limit=50")
                    for _ in range(20)
                ]
            )
            results["emails_query_20_concurrent"] = {
                "requests": len(concurrent),
                "p95_ms": round(_p95(concurrent), 2),
                "max_ms": round(max(concurrent), 2),
            }
            results["dataset"] = {
                "emails": EMAIL_COUNT,
                "applications": APPLICATION_COUNT,
                "events": EVENT_COUNT,
            }
            results["target_p95_ms"] = 500
            results["passed"] = all(
                result["p95_ms"] <= 500
                for result in results.values()
                if isinstance(result, dict) and "p95_ms" in result
            )
            return results
    finally:
        app.dependency_overrides.pop(get_settings, None)


def main() -> None:
    email_id = application_id = 0
    try:
        email_id, application_id = seed()
        result = asyncio.run(benchmark(email_id, application_id))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["passed"]:
            raise SystemExit(1)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
