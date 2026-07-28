from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.domain.enums import (
    EmailAnalysisStatus,
    EmailCategory,
    EmailPriority,
)
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.repositories.email_analysis import (
    EmailAnalysisRepository,
    EmailNotFoundError,
)


def make_analysis() -> EmailAnalysis:
    return EmailAnalysis(
        email_id=9,
        version=0,
        status=EmailAnalysisStatus.VALID,
        is_job_related=True,
        category=EmailCategory.INTERVIEW,
        priority=EmailPriority.HIGH,
        should_reply=True,
        classification_confidence=0.9,
        extraction_confidence=0.8,
        extraction_json={},
        evidence_json={},
        missing_fields=[],
        schema_version="email-analysis.v1",
    )


def test_add_version_replaces_current_version_after_locking_email() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = 9
    old = make_analysis()
    old.version = 3
    old.is_current = True
    session.scalars.return_value = [old]
    analysis = make_analysis()

    saved = EmailAnalysisRepository(session).add_version(analysis)

    assert old.is_current is False
    assert saved.version == 4
    assert saved.is_current is True
    session.add.assert_called_once_with(analysis)
    session.flush.assert_called_once_with()


def test_add_version_rejects_unknown_email() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(EmailNotFoundError):
        EmailAnalysisRepository(session).add_version(make_analysis())

    session.add.assert_not_called()
