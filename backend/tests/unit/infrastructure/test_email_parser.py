from email.message import EmailMessage

from app.domain.enums import EmailParseStatus
from app.infrastructure.email.parser import parse_email, sanitize_html


def test_mime_parser_decodes_chinese_and_keeps_only_attachment_metadata() -> None:
    message = EmailMessage()
    message["Subject"] = "面试邀请｜后端开发工程师"
    message["From"] = "招聘专员 <hr@example.com>"
    message["To"] = "候选人 <candidate@example.com>"
    message["Date"] = "Tue, 28 Jul 2026 10:00:00 +0800"
    message["Message-ID"] = "<interview-1@example.com>"
    message.set_content(
        "您好，请于周五参加面试。\n-- \n招聘团队\nOn Mon, 27 Jul 2026, candidate wrote:\n历史回复"
    )
    message.add_alternative(
        """
        <html><body onload="steal()">
          <p>您好，请参加面试。</p>
          <script>alert(1)</script>
          <img src="https://tracker.example/pixel">
          <a href="javascript:alert(1)">危险链接</a>
          <a href="https://meeting.example/room">会议链接</a>
        </body></html>
        """,
        subtype="html",
    )
    message.add_attachment(
        b"not-a-real-pdf",
        maintype="application",
        subtype="pdf",
        filename="面试说明.pdf",
    )

    parsed = parse_email(message.as_bytes())

    assert parsed.parse_status == EmailParseStatus.SUCCEEDED
    assert parsed.subject == "面试邀请｜后端开发工程师"
    assert parsed.from_name == "招聘专员"
    assert parsed.from_address == "hr@example.com"
    assert parsed.to_recipients == [{"name": "候选人", "address": "candidate@example.com"}]
    assert parsed.analysis_text == "您好，请于周五参加面试。"
    assert "script" not in parsed.html_sanitized
    assert "onload" not in parsed.html_sanitized
    assert "tracker.example" not in parsed.html_sanitized
    assert "javascript:" not in parsed.html_sanitized
    assert "https://meeting.example/room" in parsed.html_sanitized
    assert parsed.attachment_metadata == [
        {
            "filename": "面试说明.pdf",
            "content_type": "application/pdf",
            "size_bytes": 14,
            "content_id": None,
            "inline": False,
        }
    ]


def test_html_only_email_produces_safe_analysis_text() -> None:
    message = EmailMessage()
    message["From"] = "HR <hr@example.com>"
    message["To"] = "candidate@example.com"
    message.set_content(
        '<p>请在今晚前提交材料。</p><img src="https://tracking.example/1">',
        subtype="html",
    )

    parsed = parse_email(message.as_bytes())

    assert parsed.plain_body is None
    assert parsed.analysis_text == "请在今晚前提交材料。"
    assert "tracking.example" not in parsed.html_sanitized


def test_oversized_message_is_header_only_and_marked_partial() -> None:
    raw_headers = (
        b"Subject: Large attachment\r\n"
        b"From: sender@example.com\r\n"
        b"To: candidate@example.com\r\n\r\n"
    )

    parsed = parse_email(
        raw_headers,
        truncated=True,
        message_size=20 * 1024 * 1024,
    )

    assert parsed.parse_status == EmailParseStatus.PARTIAL
    assert parsed.plain_body is None
    assert parsed.attachment_metadata[0]["download_skipped"] is True


def test_sanitizer_removes_dangerous_protocols_and_remote_images() -> None:
    cleaned = sanitize_html(
        '<img src="https://remote.example/pixel">'
        '<a href="data:text/html,bad" onclick="bad()">bad</a>'
        '<a href="mailto:hr@example.com">mail</a>'
    )

    assert "img" not in cleaned
    assert "data:" not in cleaned
    assert "onclick" not in cleaned
    assert "mailto:hr@example.com" in cleaned
