from app.domain import enums
from app.infrastructure.db.models.review_task import ReviewTask


def test_review_decision_has_no_legacy_status_axis() -> None:
    assert "status" not in ReviewTask.__table__.columns
    assert not hasattr(enums, "ReviewTaskStatus")
