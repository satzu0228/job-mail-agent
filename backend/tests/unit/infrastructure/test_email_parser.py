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
    assert (
        'data-jm-remote-src="https://tracker.example/pixel"'
        in parsed.html_sanitized
    )
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
    assert (
        'data-jm-remote-src="https://tracking.example/1"'
        in parsed.html_sanitized
    )


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


def test_sanitizer_removes_dangerous_protocols_and_defers_remote_images() -> None:
    cleaned = sanitize_html(
        '<img src="https://remote.example/pixel">'
        '<a href="data:text/html,bad" onclick="bad()">bad</a>'
        '<a href="mailto:hr@example.com">mail</a>'
    )

    assert (
        '<img data-jm-remote-src="https://remote.example/pixel"'
        in cleaned
    )
    assert "data:" not in cleaned
    assert "onclick" not in cleaned
    assert "mailto:hr@example.com" in cleaned


def test_sanitizer_keeps_cid_and_limited_data_images() -> None:
    cleaned = sanitize_html(
        '<img src="cid:company-logo" alt="公司标志">'
        '<img src="data:image/png;base64,aGVsbG8=" alt="内嵌图片">'
        '<img src="data:image/svg+xml;base64,PHN2Zz4=" alt="危险图片">'
    )

    assert 'data-jm-cid="company-logo"' in cleaned
    assert 'src="data:image/png;base64,aGVsbG8="' in cleaned
    assert "data:image/svg+xml" not in cleaned
    assert 'loading="lazy"' in cleaned


def test_mime_parser_indexes_related_cid_image_for_safe_display() -> None:
    message = EmailMessage()
    message["From"] = "HR <hr@example.com>"
    message["To"] = "candidate@example.com"
    message.set_content("面试邀请")
    message.add_alternative(
        '<p>面试邀请</p><img src="cid:company-logo" alt="公司标志">',
        subtype="html",
    )
    html_part = message.get_payload()[-1]
    html_part.add_related(
        b"\x89PNG\r\n\x1a\nfixture",
        maintype="image",
        subtype="png",
        cid="<company-logo>",
        disposition="inline",
        filename="logo.png",
    )

    parsed = parse_email(message.as_bytes())

    assert 'data-jm-cid="company-logo"' in parsed.html_sanitized
    assert parsed.attachment_metadata == [
        {
            "filename": "logo.png",
            "content_type": "image/png",
            "size_bytes": 15,
            "content_id": "<company-logo>",
            "inline": True,
        }
    ]


def test_sanitizer_keeps_safe_email_layout_and_button_styles() -> None:
    cleaned = sanitize_html(
        """
        <style>.button { position: fixed; inset: 0; }</style>
        <table width="100%" cellpadding="16" cellspacing="0" bgcolor="#f5f7fa">
          <tr>
            <td align="center" style="padding: 20px; position: fixed">
              <a
                href="https://jobs.example.com/interview"
                class="button"
                style="
                  display: inline-block;
                  padding: 12px 24px;
                  color: #ffffff;
                  background-color: #3370ff;
                  border-radius: 6px;
                  background-image: url(https://tracker.example/pixel);
                "
              >确认面试</a>
            </td>
          </tr>
        </table>
        """
    )

    assert '<table width="100%" cellpadding="16" cellspacing="0"' in cleaned
    assert 'bgcolor="#f5f7fa"' in cleaned
    assert 'style="padding: 20px"' in cleaned
    assert "display: inline-block" in cleaned
    assert "background-color: #3370ff" in cleaned
    assert "border-radius: 6px" in cleaned
    assert 'target="_blank"' in cleaned
    assert "position" not in cleaned
    assert "tracker.example" not in cleaned
    assert "<style>.button {}</style>" in cleaned
    assert 'class="button"' in cleaned


def test_sanitizer_keeps_responsive_css_that_hides_duplicate_mobile_markup() -> None:
    cleaned = sanitize_html(
        """
        <style>
          .desktop { display: block !important; width: 640px; }
          .mobile { display: none !important; width: 320px; }
          .tracking { background-image: url(https://tracker.example/pixel); }
          @media (max-width: 600px) {
            .desktop { display: none !important; }
            .mobile { display: block !important; }
          }
        </style>
        <div class="desktop">通知内容</div>
        <div class="mobile">通知内容</div>
        """
    )

    assert 'class="desktop"' in cleaned
    assert 'class="mobile"' in cleaned
    assert ".desktop {display: block !important; width: 640px}" in cleaned
    assert ".mobile {display: none !important; width: 320px}" in cleaned
    assert "@media (max-width: 600px)" in cleaned
    assert "tracker.example" not in cleaned
