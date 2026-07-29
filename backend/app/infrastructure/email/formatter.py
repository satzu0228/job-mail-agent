from __future__ import annotations

import re
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any

_EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)


class EmailFormattingError(ValueError):
    """确定性邮件格式化或地址校验失败。"""


def reply_subject(original_subject: str) -> str:
    subject = _single_line(original_subject, field_name="subject").strip()
    if not subject:
        raise EmailFormattingError("原邮件主题为空")
    if re.match(r"^\s*(re|回复)\s*:", subject, re.IGNORECASE):
        return subject[:998]
    return f"Re: {subject}"[:998]


def format_reply_body(
    core_body: str,
    *,
    sender_name: str | None,
    user_display_name: str,
    language: str = "zh-CN",
) -> str:
    body = core_body.strip()
    if not body:
        raise EmailFormattingError("回复正文为空")
    addressee = (sender_name or "").strip()
    signature = user_display_name.strip()
    if not signature:
        raise EmailFormattingError("用户显示名称为空")
    if language == "en":
        salutation = f"Dear {addressee}," if addressee else "Hello,"
        return f"{salutation}\n\n{body}\n\nSincerely,\n{signature}"
    if language != "zh-CN":
        raise EmailFormattingError("回复语言不受支持")
    salutation = f"尊敬的{addressee}：" if addressee else "您好："
    return f"{salutation}\n\n{body}\n\n此致\n敬礼！\n\n{signature}"


def recipient(address: str, name: str | None = None) -> dict[str, str]:
    normalized = _valid_address(address)
    result = {"address": normalized}
    clean_name = _single_line(name or "", field_name="recipient name").strip()
    if clean_name:
        result["name"] = clean_name
    return result


def build_message(
    *,
    from_address: str,
    from_name: str | None,
    to_recipients: list[dict[str, Any]],
    cc_recipients: list[dict[str, Any]],
    subject: str,
    body: str,
    in_reply_to: str | None,
) -> EmailMessage:
    if not to_recipients:
        raise EmailFormattingError("收件人为空")
    message = EmailMessage()
    message["From"] = _address_object({"address": from_address, "name": from_name or ""})
    message["To"] = [_address_object(item) for item in to_recipients]
    if cc_recipients:
        message["Cc"] = [_address_object(item) for item in cc_recipients]
    message["Subject"] = _single_line(subject, field_name="subject")
    message["Message-ID"] = make_msgid(domain=from_address.rsplit("@", 1)[-1])
    if in_reply_to:
        reference = _single_line(in_reply_to, field_name="message id").strip()
        if reference:
            message["In-Reply-To"] = reference
            message["References"] = reference
    message.set_content(body, subtype="plain", charset="utf-8")
    return message


def _address_object(value: dict[str, Any]) -> Address:
    raw_address = value.get("address")
    if not isinstance(raw_address, str):
        raise EmailFormattingError("收件人地址格式无效")
    address = _valid_address(raw_address)
    name_value = value.get("name", "")
    if not isinstance(name_value, str):
        raise EmailFormattingError("收件人名称格式无效")
    name = _single_line(name_value, field_name="recipient name").strip()
    local, domain = address.rsplit("@", 1)
    return Address(display_name=name, username=local, domain=domain)


def _valid_address(value: str) -> str:
    address = _single_line(value, field_name="email address").strip()
    if len(address) > 320 or not _EMAIL_PATTERN.fullmatch(address):
        raise EmailFormattingError("邮件地址格式无效")
    return address


def _single_line(value: str, *, field_name: str) -> str:
    if "\r" in value or "\n" in value:
        raise EmailFormattingError(f"{field_name} 包含非法换行")
    return value
