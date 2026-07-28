from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html import escape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from app.domain.enums import EmailParseStatus

_ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
_SKIP_CONTENT_TAGS = {
    "applet",
    "canvas",
    "embed",
    "form",
    "head",
    "object",
    "script",
    "style",
    "svg",
}
_GLOBAL_ATTRIBUTES = {"dir", "lang", "title"}
_TAG_ATTRIBUTES = {
    "a": {"href"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
_QUOTE_MARKERS = (
    re.compile(r"^\s*On .+ wrote:\s*$", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*发件人[:：]"),
    re.compile(r"^\s*在 .+写道[:：]\s*$"),
)
_SIGNATURE_MARKERS = (
    re.compile(r"^\s*--\s*$"),
    re.compile(r"^\s*Sent from my ", re.IGNORECASE),
    re.compile(r"^\s*从我的.+发送\s*$"),
)


@dataclass(frozen=True)
class ParsedEmail:
    message_id: str | None
    subject: str
    from_name: str | None
    from_address: str
    reply_to_address: str | None
    to_recipients: list[dict[str, str | None]]
    cc_recipients: list[dict[str, str | None]]
    sent_at: datetime | None
    received_at: datetime | None
    plain_body: str | None
    html_sanitized: str | None
    analysis_text: str
    attachment_metadata: list[dict[str, Any]]
    parse_status: EmailParseStatus


class _SafeHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        if tag in _SKIP_CONTENT_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth or tag == "img" or tag not in _ALLOWED_TAGS:
            return
        safe_attrs = []
        allowed = _GLOBAL_ATTRIBUTES | _TAG_ATTRIBUTES.get(tag, set())
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or value is None or name.startswith("on"):
                continue
            if name == "href" and not _safe_url(value):
                continue
            safe_attrs.append(f' {name}="{escape(value, quote=True)}"')
        if tag == "a":
            safe_attrs.append(' rel="nofollow noopener noreferrer"')
        self.parts.append(f"<{tag}{''.join(safe_attrs)}>")

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() in _ALLOWED_TAGS and tag.lower() not in {"br", "hr"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_CONTENT_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if not self.skip_depth and tag in _ALLOWED_TAGS and tag not in {"br", "hr"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(escape(data))


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() in {"br", "div", "li", "p", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"div", "li", "p", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def sanitize_html(value: str) -> str:
    sanitizer = _SafeHtmlParser()
    sanitizer.feed(value)
    sanitizer.close()
    return "".join(sanitizer.parts).strip()


def parse_email(
    raw_message: bytes,
    *,
    received_at: datetime | None = None,
    truncated: bool = False,
    message_size: int | None = None,
) -> ParsedEmail:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    sender = _addresses(message.get_all("From", []))
    to_recipients = _addresses(message.get_all("To", []))
    cc_recipients = _addresses(message.get_all("Cc", []))
    reply_to = _addresses(message.get_all("Reply-To", []))
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict[str, Any]] = []
    partial = truncated

    if not truncated:
        plain_part = message.get_body(preferencelist=("plain",))
        html_part = message.get_body(preferencelist=("html",))
        for part, target in ((plain_part, plain_parts), (html_part, html_parts)):
            if part is None:
                continue
            try:
                content = part.get_content()
                if isinstance(content, str):
                    target.append(content)
            except (LookupError, UnicodeError, ValueError):
                partial = True
        for part in message.iter_attachments():
            payload = part.get_payload(decode=True)
            attachments.append(
                {
                    "filename": part.get_filename(),
                    "content_type": part.get_content_type(),
                    "size_bytes": (
                        len(payload)
                        if payload is not None
                        else len(part.as_bytes(policy=policy.default))
                    ),
                    "content_id": part.get("Content-ID"),
                    "inline": part.get_content_disposition() == "inline",
                }
            )
    elif message_size is not None:
        attachments.append(
            {
                "filename": None,
                "content_type": "message/rfc822",
                "size_bytes": message_size,
                "content_id": None,
                "inline": False,
                "download_skipped": True,
            }
        )

    plain_body = _join_parts(plain_parts)
    html_sanitized = sanitize_html(_join_parts(html_parts) or "") or None
    analysis_source = plain_body or _html_to_text(html_sanitized or "")
    analysis_text = _strip_quote_and_signature(analysis_source)
    from_name, from_address = sender[0] if sender else (None, "")
    if not from_address:
        partial = True
        from_address = "unknown@invalid.local"
    if not analysis_text and not truncated:
        partial = True

    return ParsedEmail(
        message_id=_clean_message_id(message.get("Message-ID")),
        subject=str(message.get("Subject") or "(无主题)").strip() or "(无主题)",
        from_name=from_name,
        from_address=from_address,
        reply_to_address=reply_to[0][1] if reply_to else None,
        to_recipients=_address_objects(to_recipients),
        cc_recipients=_address_objects(cc_recipients),
        sent_at=_parse_date(message),
        received_at=received_at or _parse_date(message),
        plain_body=plain_body,
        html_sanitized=html_sanitized,
        analysis_text=analysis_text,
        attachment_metadata=attachments,
        parse_status=(EmailParseStatus.PARTIAL if partial else EmailParseStatus.SUCCEEDED),
    )


def _safe_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme.lower() in {"http", "https", "mailto"} and bool(
        parsed.netloc or parsed.scheme == "mailto"
    )


def _addresses(headers: list[str | Message]) -> list[tuple[str | None, str]]:
    return [
        (name.strip() or None, address.strip().lower())
        for name, address in getaddresses([str(value) for value in headers])
        if address.strip()
    ]


def _address_objects(
    values: list[tuple[str | None, str]],
) -> list[dict[str, str | None]]:
    return [{"name": name, "address": address} for name, address in values]


def _parse_date(message: EmailMessage) -> datetime | None:
    value = message.get("Date")
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _clean_message_id(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:998] or None


def _join_parts(values: list[str]) -> str | None:
    cleaned = [value.strip() for value in values if value.strip()]
    return "\n\n".join(cleaned) if cleaned else None


def _html_to_text(value: str) -> str:
    parser = _HtmlTextParser()
    parser.feed(value)
    parser.close()
    return re.sub(r"\n{3,}", "\n\n", "".join(parser.parts)).strip()


def _strip_quote_and_signature(value: str | None) -> str:
    if not value:
        return ""
    kept: list[str] = []
    for line in value.splitlines():
        if any(pattern.search(line) for pattern in (*_QUOTE_MARKERS, *_SIGNATURE_MARKERS)):
            break
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
