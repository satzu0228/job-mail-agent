"""IMAP、SMTP 与 MIME 解析适配器。"""

from app.infrastructure.email.client import (
    EmailConnectionError,
    ImapMailboxClient,
    RemoteEmail,
    SmtpConnectionTester,
)
from app.infrastructure.email.parser import ParsedEmail, parse_email

__all__ = [
    "EmailConnectionError",
    "ImapMailboxClient",
    "ParsedEmail",
    "RemoteEmail",
    "SmtpConnectionTester",
    "parse_email",
]
