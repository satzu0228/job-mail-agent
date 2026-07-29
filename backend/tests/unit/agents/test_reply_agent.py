import pytest
from pydantic import ValidationError

from app.agents.reply.schemas import ReplyAgentOutput


def test_reply_output_requires_body_only_when_reply_is_needed() -> None:
    output = ReplyAgentOutput(
        should_reply=True,
        confidence=0.9,
        reason="需要确认面试安排。",
        body="感谢邀请，我会按时参加。",
        facts_used=["面试邀请", "面试邀请"],
    )

    assert output.body == "感谢邀请，我会按时参加。"
    assert output.facts_used == ["面试邀请"]

    with pytest.raises(ValidationError):
        ReplyAgentOutput(
            should_reply=True,
            confidence=0.9,
            reason="需要回复。",
        )

    with pytest.raises(ValidationError):
        ReplyAgentOutput(
            should_reply=False,
            confidence=0.9,
            reason="无需回复。",
            body="多余正文",
        )


def test_reply_output_rejects_embedded_mail_headers() -> None:
    with pytest.raises(ValidationError):
        ReplyAgentOutput(
            should_reply=True,
            confidence=0.8,
            reason="需要回复。",
            body="感谢邀请。\nSubject: injected",
        )

    with pytest.raises(ValidationError):
        ReplyAgentOutput(
            should_reply=True,
            confidence=0.8,
            reason="需要回复。",
            body="您好：\n\n感谢邀请。",
        )
