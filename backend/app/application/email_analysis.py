from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.agents.classification.schemas import ClassificationOutput
from app.agents.extraction.schemas import ExtractionOutput
from app.domain.enums import EmailAnalysisStatus
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.repositories.email_analysis import EmailAnalysisRepository

ANALYSIS_SCHEMA_VERSION = "email-analysis.v1"


@dataclass(frozen=True, slots=True)
class PersistedEmailAnalysis:
    id: int
    email_id: int
    version: int
    status: EmailAnalysisStatus
    is_current: bool


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


def build_email_analysis(
    *,
    email_id: int,
    classification: ClassificationOutput,
    extraction: ExtractionOutput | None,
    workflow_run_id: str | None = None,
) -> EmailAnalysis:
    if classification.is_job_related and extraction is None:
        raise ValueError("job-related analysis requires extraction output")
    if not classification.is_job_related and extraction is not None:
        raise ValueError("non-job analysis cannot contain extraction output")

    extraction_payload = (
        extraction.model_dump(mode="json", exclude_none=True) if extraction else {}
    )
    evidence = {
        "classification": [
            item.model_dump(mode="json") for item in classification.evidence
        ],
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
        extraction_confidence=(
            Decimal(str(extraction.overall_confidence)) if extraction else None
        ),
        summary=extraction.summary if extraction else None,
        company_name=extraction.company.value if extraction and extraction.company else None,
        position_name=(
            extraction.position.value if extraction and extraction.position else None
        ),
        event_type=(
            extraction.event_type.value if extraction and extraction.event_type else None
        ),
        event_time=_as_utc_naive(
            extraction.event_time.normalized
            if extraction and extraction.event_time
            else None
        ),
        deadline_at=_as_utc_naive(
            extraction.deadline.normalized
            if extraction and extraction.deadline
            else None
        ),
        source_timezone=_source_timezone(extraction),
        extraction_json=extraction_payload,
        evidence_json=evidence,
        missing_fields=(
            [field.value for field in extraction.missing_fields] if extraction else []
        ),
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
            evidence[field_name] = [
                item.model_dump(mode="json") for item in value.evidence
            ]
    if extraction.materials:
        evidence["materials"] = [
            item.model_dump(mode="json")
            for material in extraction.materials
            for item in material.evidence
        ]
    return evidence
