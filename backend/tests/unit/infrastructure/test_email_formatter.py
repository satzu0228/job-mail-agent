import pytest

from app.infrastructure.email.formatter import (
    EmailFormattingError,
    build_message,
    format_reply_body,
    recipient,
    reply_subject,
)


def test_formatter_adds_subject_salutation_and_signature_once() -> None:
    body = format_reply_body(
        "感谢您的邀请，我会按时参加面试。",
        sender_name="李老师",
        user_display_name="张三",
    )
    message = build_message(
        from_address="candidate@example.com",
        from_name="张三",
        to_recipients=[recipient("hr@example.com", "李老师")],
        cc_recipients=[],
        subject=reply_subject("面试邀请"),
        body=body,
        in_reply_to="<source@example.com>",
    )

    assert message["Subject"] == "Re: 面试邀请"
    assert message["In-Reply-To"] == "<source@example.com>"
    assert body.count("尊敬的李老师：") == 1
    assert body.count("张三") == 1
    assert "感谢您的邀请" in message.get_content()


def test_formatter_blocks_header_injection_and_invalid_address() -> None:
    with pytest.raises(EmailFormattingError):
        reply_subject("面试邀请\r\nBcc: attacker@example.com")

    with pytest.raises(EmailFormattingError):
        recipient("not-an-email")


def test_formatter_uses_deterministic_english_envelope_text() -> None:
    body = format_reply_body(
        "Thank you for the invitation. I will attend.",
        sender_name="Alice",
        user_display_name="Zhang San",
        language="en",
    )

    assert body.startswith("Dear Alice,")
    assert body.endswith("Sincerely,\nZhang San")
