from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.agents.classification.agent import ClassificationAgent
from app.agents.classification.schemas import (
    ClassificationInput,
    ClassificationOutput,
)
from app.agents.common.schemas import AttachmentMetadata, PreparedEmail
from app.agents.extraction.agent import ExtractionAgent
from app.agents.extraction.schemas import (
    ExtractionInput,
    ExtractionOutput,
)
from app.domain.enums import EmailAnalysisStatus, EmailParseStatus, RequiredCapability
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.business import EmailRepository
from app.infrastructure.db.repositories.email_analysis import EmailAnalysisRepository

ANALYSIS_SCHEMA_VERSION = "email-analysis.v1"


@dataclass(frozen=True, slots=True)
class PersistedEmailAnalysis:
    id: int
    email_id: int
    version: int
    status: EmailAnalysisStatus
    is_current: bool


@dataclass(frozen=True, slots=True)
class CompletedEmailAnalysis:
    analysis: EmailAnalysis
    classification: ClassificationOutput
    extraction: ExtractionOutput | None


class ClassificationRunner(Protocol):
    def run(self, agent_input: ClassificationInput) -> ClassificationOutput: ...


class ExtractionRunner(Protocol):
    def run(self, agent_input: ExtractionInput) -> ExtractionOutput: ...


class EmailNotReadyForAnalysisError(RuntimeError):
    """邮件解析事实不足，不能安全调用模型。"""


class NonJobEmailExtractionError(RuntimeError):
    """非求职邮件不进入结构化求职信息抽取。"""


class EmailModelExecutionError(RuntimeError):
    """模型调用或结构化输出校验失败，对外不暴露底层输入与异常。"""


class SingleEmailAnalysisService:
    def __init__(
        self,
        session: Session,
        user_id: int,
        classification_agent: ClassificationRunner,
        extraction_agent: ExtractionRunner,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._classification_agent = classification_agent
        self._extraction_agent = extraction_agent
        self._emails = EmailRepository(session, user_id)
        self._analyses = EmailAnalysisRepository(session)

    @classmethod
    def from_agents(
        cls,
        session: Session,
        user_id: int,
        classification_agent: ClassificationAgent,
        extraction_agent: ExtractionAgent,
    ) -> SingleEmailAnalysisService:
        return cls(
            session,
            user_id,
            classification_agent,
            extraction_agent,
        )

    def classify(self, email_id: int) -> ClassificationOutput:
        prepared = self._prepare_email(email_id)
        return self._run_classification(prepared)

    def extract(self, email_id: int) -> ExtractionOutput:
        prepared = self._prepare_email(email_id)
        classification = self._run_classification(prepared)
        if not classification.is_job_related:
            raise NonJobEmailExtractionError("非求职邮件不执行求职信息抽取")
        return self._run_extraction(prepared, classification)

    def analyze(self, email_id: int) -> CompletedEmailAnalysis:
        prepared = self._prepare_email(email_id)
        classification = self._run_classification(prepared)
        extraction = (
            self._run_extraction(prepared, classification)
            if classification.is_job_related
            else None
        )
        analysis = build_email_analysis(
            email_id=email_id,
            classification=classification,
            extraction=extraction,
        )
        with self._session.begin():
            saved = self._analyses.add_version(analysis)
        return CompletedEmailAnalysis(
            analysis=saved,
            classification=classification,
            extraction=extraction,
        )

    def _prepare_email(self, email_id: int) -> PreparedEmail:
        email = self._emails.get(email_id)
        if (
            email.parse_status not in {EmailParseStatus.SUCCEEDED, EmailParseStatus.PARTIAL}
            or not email.analysis_text.strip()
        ):
            self._session.rollback()
            raise EmailNotReadyForAnalysisError("邮件尚未成功解析，不能启动 AI 分析")
        user = self._session.get(User, self._user_id)
        user_timezone = user.timezone if user is not None else "Asia/Shanghai"
        try:
            prepared = prepare_email(email, user_timezone=user_timezone)
        except ValueError as exc:
            self._session.rollback()
            raise EmailNotReadyForAnalysisError("邮件事实不符合分析输入要求") from exc
        # 模型调用期间不持有数据库事务或连接锁。
        self._session.rollback()
        return prepared

    def _run_classification(
        self,
        prepared: PreparedEmail,
    ) -> ClassificationOutput:
        try:
            return self._classification_agent.run(ClassificationInput(email=prepared))
        except Exception as exc:
            raise EmailModelExecutionError("邮件分类模型执行失败") from exc

    def _run_extraction(
        self,
        prepared: PreparedEmail,
        classification: ClassificationOutput,
    ) -> ExtractionOutput:
        try:
            return self._extraction_agent.run(
                ExtractionInput(
                    email=prepared,
                    classification=classification,
                )
            )
        except Exception as exc:
            raise EmailModelExecutionError("邮件抽取模型执行失败") from exc


class PersistEmailAnalysis:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def execute(
        self,
        *,
        email_id: int,
        classification: ClassificationOutput,
        extraction: ExtractionOutput | None,
        workflow_run_id: str | None = None,
    ) -> PersistedEmailAnalysis:
        analysis = build_email_analysis(
            email_id=email_id,
            classification=classification,
            extraction=extraction,
            workflow_run_id=workflow_run_id,
        )
        with self._session_factory() as session, session.begin():
            saved = EmailAnalysisRepository(session).add_version(analysis)
            result = PersistedEmailAnalysis(
                id=saved.id,
                email_id=saved.email_id,
                version=saved.version,
                status=saved.status,
                is_current=saved.is_current,
            )
        return result


def prepare_email(email: Email, *, user_timezone: str) -> PreparedEmail:
    attachments = [
        attachment
        for item in email.attachment_metadata[:50]
        if (attachment := _attachment_metadata(item)) is not None
    ]
    return PreparedEmail(
        email_id=email.id,
        message_id=email.message_id,
        subject=email.subject,
        sender_name=email.from_name,
        sender_address=email.from_address,
        sent_at=_as_aware_utc(email.sent_at),
        received_at=_as_aware_utc(email.received_at),
        analysis_text=email.analysis_text,
        attachments=attachments,
        user_timezone=user_timezone,
    )


def build_email_analysis(
    *,
    email_id: int,
    classification: ClassificationOutput,
    extraction: ExtractionOutput | None,
    workflow_run_id: str | None = None,
) -> EmailAnalysis:
    extraction_required = (
        RequiredCapability.EXTRACT in classification.required_capabilities
    )
    if extraction_required and extraction is None:
        raise ValueError("job-related analysis requires extraction output")
    if not classification.is_job_related and extraction is not None:
        raise ValueError("non-job analysis cannot contain extraction output")

    extraction_payload = extraction.model_dump(mode="json", exclude_none=True) if extraction else {}
    evidence = {
        "classification": [item.model_dump(mode="json") for item in classification.evidence],
        "extraction": _collect_extraction_evidence(extraction),
    }
    status = _derive_status(classification, extraction)

    return EmailAnalysis(
        email_id=email_id,
        workflow_run_id=workflow_run_id,
        version=0,
        is_current=True,
        status=status,
        is_job_related=classification.is_job_related,
        category=classification.category,
        priority=classification.priority,
        should_reply=classification.should_reply,
        classification_confidence=Decimal(str(classification.confidence)),
        extraction_confidence=(Decimal(str(extraction.overall_confidence)) if extraction else None),
        summary=extraction.summary if extraction else None,
        company_name=extraction.company.value if extraction and extraction.company else None,
        position_name=(extraction.position.value if extraction and extraction.position else None),
        event_type=(extraction.event_type.value if extraction and extraction.event_type else None),
        event_time=_as_utc_naive(
            extraction.event_time.normalized if extraction and extraction.event_time else None
        ),
        deadline_at=_as_utc_naive(
            extraction.deadline.normalized if extraction and extraction.deadline else None
        ),
        source_timezone=_source_timezone(extraction),
        extraction_json=extraction_payload,
        evidence_json=evidence,
        missing_fields=([field.value for field in extraction.missing_fields] if extraction else []),
        schema_version=ANALYSIS_SCHEMA_VERSION,
    )


def _derive_status(
    classification: ClassificationOutput,
    extraction: ExtractionOutput | None,
) -> EmailAnalysisStatus:
    if classification.uncertainties:
        return EmailAnalysisStatus.PENDING_CONFIRMATION
    if extraction is None:
        return EmailAnalysisStatus.VALID
    if extraction.uncertainties:
        return EmailAnalysisStatus.PENDING_CONFIRMATION
    if any(
        value and value.requires_human_confirmation
        for value in (extraction.event_time, extraction.deadline)
    ):
        return EmailAnalysisStatus.PENDING_CONFIRMATION
    return EmailAnalysisStatus.VALID


def _as_utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("normalized datetime must include a UTC offset")
    return value.astimezone(UTC).replace(tzinfo=None)


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _attachment_metadata(item: dict[str, Any]) -> AttachmentMetadata | None:
    filename = item.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        return None
    content_type = item.get("content_type")
    size_bytes = item.get("size_bytes")
    try:
        return AttachmentMetadata(
            filename=filename,
            content_type=content_type if isinstance(content_type, str) else None,
            size_bytes=(
                size_bytes
                if isinstance(size_bytes, int)
                and not isinstance(size_bytes, bool)
                and size_bytes >= 0
                else None
            ),
        )
    except (TypeError, ValueError):
        return None


def _source_timezone(extraction: ExtractionOutput | None) -> str | None:
    if extraction is None:
        return None
    if extraction.event_time and extraction.event_time.timezone:
        return extraction.event_time.timezone
    if extraction.deadline and extraction.deadline.timezone:
        return extraction.deadline.timezone
    return None


def _collect_extraction_evidence(
    extraction: ExtractionOutput | None,
) -> dict[str, list[dict[str, Any]]]:
    if extraction is None:
        return {}

    evidence: dict[str, list[dict[str, Any]]] = {}
    field_names = (
        "company",
        "position",
        "proposed_stage",
        "event_type",
        "contact_name",
        "contact_email",
        "event_time",
        "deadline",
        "location",
        "meeting_url",
    )
    for field_name in field_names:
        value = getattr(extraction, field_name)
        if value is not None:
            evidence[field_name] = [item.model_dump(mode="json") for item in value.evidence]
    if extraction.materials:
        evidence["materials"] = [
            item.model_dump(mode="json")
            for material in extraction.materials
            for item in material.evidence
        ]
    return evidence
