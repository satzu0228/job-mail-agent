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
    "center",
    "code",
    "div",
    "em",
    "font",
    "h1",
    "h2",
    "h3",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "style",
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
    "object",
    "script",
    "svg",
}
_GLOBAL_ATTRIBUTES = {"align", "class", "dir", "id", "lang", "style", "title"}
_TAG_ATTRIBUTES = {
    "a": {"href"},
    "font": {"color", "face", "size"},
    "img": {"alt", "height", "src", "width"},
    "table": {"bgcolor", "border", "cellpadding", "cellspacing", "width"},
    "td": {"bgcolor", "colspan", "height", "rowspan", "valign", "width"},
    "th": {"bgcolor", "colspan", "height", "rowspan", "valign", "width"},
}
_VOID_TAGS = {"br", "hr", "img"}
_SAFE_DATA_IMAGE = re.compile(
    r"^data:image/(?:gif|jpe?g|png|webp);base64,[a-z0-9+/=\s]+$",
    re.IGNORECASE,
)
_MAX_DATA_IMAGE_LENGTH = 2_800_000
_ALLOWED_STYLE_PROPERTIES = {
    "background",
    "background-color",
    "border",
    "border-bottom",
    "border-color",
    "border-left",
    "border-radius",
    "border-right",
    "border-style",
    "border-top",
    "border-width",
    "box-sizing",
    "color",
    "display",
    "font",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "height",
    "letter-spacing",
    "line-height",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-height",
    "max-width",
    "min-height",
    "min-width",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "overflow",
    "overflow-x",
    "overflow-y",
    "table-layout",
    "text-align",
    "text-decoration",
    "text-indent",
    "text-transform",
    "vertical-align",
    "white-space",
    "width",
    "visibility",
    "word-break",
    "word-spacing",
    "word-wrap",
}
_ALLOWED_DISPLAY_VALUES = {
    "block",
    "flex",
    "grid",
    "inline",
    "inline-block",
    "inline-flex",
    "none",
    "table",
    "table-cell",
    "table-row",
}
_DANGEROUS_STYLE_VALUE = re.compile(
    r"(?:url\s*\(|expression\s*\(|@import|javascript\s*:|"
    r"https?\s*:|data\s*:|//|-moz-binding|behavior\s*:|"
    r"-webkit-image-set|image-set\s*\(|[\\<>])",
    re.IGNORECASE,
)
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
        self.style_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        if tag in _SKIP_CONTENT_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in _ALLOWED_TAGS:
            return
        if tag == "style":
            self.style_depth += 1
            self.parts.append("<style>")
            return
        safe_attrs = []
        allowed = _GLOBAL_ATTRIBUTES | _TAG_ATTRIBUTES.get(tag, set())
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or value is None or name.startswith("on"):
                continue
            if name == "href" and not _safe_url(value):
                continue
            if tag == "img" and name == "src":
                image_source = _sanitize_image_source(value)
                if image_source is None:
                    continue
                name, value = image_source
            if name == "style":
                value = _sanitize_style(value)
                if not value:
                    continue
            safe_attrs.append(f' {name}="{escape(value, quote=True)}"')
        if tag == "img":
            if not any(
                attribute.startswith(
                    (' src="', ' data-jm-cid="', ' data-jm-remote-src="')
                )
                for attribute in safe_attrs
            ):
                return
            safe_attrs.extend((' loading="lazy"', ' decoding="async"'))
        if tag == "a":
            safe_attrs.append(
                ' target="_blank" rel="nofollow noopener noreferrer"'
            )
        self.parts.append(f"<{tag}{''.join(safe_attrs)}>")

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() in _ALLOWED_TAGS and tag.lower() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_CONTENT_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag == "style" and self.style_depth:
            self.style_depth -= 1
            self.parts.append("</style>")
            return
        if not self.skip_depth and tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.style_depth:
            self.parts.append(_sanitize_stylesheet(data))
            return
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


def _sanitize_style(value: str) -> str:
    """保留邮件排版所需的安全内联样式，拒绝外部资源和越界定位能力。"""
    without_comments = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL)
    safe_declarations: list[str] = []
    for declaration in without_comments.split(";"):
        name, separator, raw_value = declaration.partition(":")
        if not separator:
            continue
        name = name.strip().lower()
        css_value = raw_value.strip()
        if (
            name not in _ALLOWED_STYLE_PROPERTIES
            or not css_value
            or len(css_value) > 512
            or _DANGEROUS_STYLE_VALUE.search(css_value)
        ):
            continue
        if name == "display":
            display_value = re.sub(
                r"\s*!important\s*$",
                "",
                css_value,
                flags=re.IGNORECASE,
            ).strip()
            if display_value.lower() not in _ALLOWED_DISPLAY_VALUES:
                continue
        safe_declarations.append(f"{name}: {css_value}")
    return "; ".join(safe_declarations)


def _sanitize_stylesheet(value: str) -> str:
    """保留响应式邮件 CSS，同时移除外链资源和非白名单声明。"""
    stylesheet = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL)
    stylesheet = re.sub(
        r"@import\b[^;]*(?:;|$)",
        "",
        stylesheet,
        flags=re.IGNORECASE,
    )
    stylesheet = re.sub(
        r"@font-face\s*\{[^{}]*\}",
        "",
        stylesheet,
        flags=re.IGNORECASE,
    )
    stylesheet = stylesheet.replace("<", "").replace(">", "")

    declaration_block = re.compile(r"\{([^{}]*)\}")

    def clean_block(match: re.Match[str]) -> str:
        return "{" + _sanitize_style(match.group(1)) + "}"

    return declaration_block.sub(clean_block, stylesheet)


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
        for part in attachment_parts(message):
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


def _sanitize_image_source(value: str) -> tuple[str, str] | None:
    source = value.strip()
    lowered = source.lower()
    if lowered.startswith("cid:"):
        content_id = source[4:].strip().strip("<>")
        if content_id and len(content_id) <= 512 and not any(
            ord(character) < 32 for character in content_id
        ):
            return "data-jm-cid", content_id
        return None
    if (
        len(source) <= _MAX_DATA_IMAGE_LENGTH
        and _SAFE_DATA_IMAGE.fullmatch(source)
    ):
        return "src", source
    if source.startswith("//"):
        source = f"https:{source}"
    parsed = urlparse(source)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        return "data-jm-remote-src", source
    return None


def attachment_parts(message: Message) -> list[Message]:
    """按稳定顺序返回普通附件和带 Content-ID 的内嵌资源。"""
    parts: list[Message] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        disposition = part.get_content_disposition()
        if (
            disposition in {"attachment", "inline"}
            or part.get_filename()
            or part.get("Content-ID")
        ):
            parts.append(part)
    return parts


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
