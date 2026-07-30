"""IMAP、SMTP 与 MIME 解析适配器。"""

from app.infrastructure.email.client import (
    EmailConnectionError,
    ImapMailboxClient,
    RemoteEmail,
    SmtpConnectionTester,
    SmtpDeliveryFailedError,
    SmtpDeliveryUnknownError,
    SmtpMailer,
)
from app.infrastructure.email.formatter import (
    EmailFormattingError,
    build_message,
    format_reply_body,
    recipient,
    reply_subject,
)
from app.infrastructure.email.parser import ParsedEmail, attachment_parts, parse_email

__all__ = [
    "EmailConnectionError",
    "EmailFormattingError",
    "ImapMailboxClient",
    "ParsedEmail",
    "RemoteEmail",
    "SmtpConnectionTester",
    "SmtpDeliveryFailedError",
    "SmtpDeliveryUnknownError",
    "SmtpMailer",
    "build_message",
    "attachment_parts",
    "format_reply_body",
    "parse_email",
    "recipient",
    "reply_subject",
]
