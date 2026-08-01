from __future__ import annotations

import imaplib
import re
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from app.domain.enums import TransportSecurity
from app.infrastructure.db.models.email_account import EmailAccount

_SIZE_PATTERN = re.compile(rb"RFC822\.SIZE\s+(\d+)", re.IGNORECASE)
_INTERNAL_DATE_PATTERN = re.compile(rb'INTERNALDATE\s+"([^"]+)"', re.IGNORECASE)
_NETEASE_IMAP_HOSTS = {"imap.163.com", "imap.126.com", "imap.yeah.net"}
_NETEASE_CLIENT_ID = (
    '("name" "JobMailAgent" "version" "0.1" "vendor" "local-project")'
)


class EmailConnectionError(RuntimeError):
    """邮箱服务器连接或认证失败，异常文本不得包含凭据。"""


class SmtpDeliveryFailedError(RuntimeError):
    """SMTP 明确拒绝发送，服务端未接受邮件。"""


class SmtpDeliveryUnknownError(RuntimeError):
    """SMTP 会话在提交期间中断，无法确认服务端是否已接受邮件。"""


class ImapMoveUnknownError(RuntimeError):
    """IMAP 已接受移动命令，但未返回可验证的新 UID。"""


@dataclass(frozen=True)
class RemoteEmail:
    uid: int
    raw_message: bytes
    received_at: datetime | None
    truncated: bool = False
    message_size: int | None = None


@dataclass(frozen=True)
class ImapMoveResult:
    folder: str
    uid_validity: int
    uid: int


class ImapMailboxClient:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    def test_connection(self, account: EmailAccount, credential: str) -> None:
        client = self._connect(account)
        try:
            client.login(account.email_address, credential)
            self._identify_client(client, account)
            status, _ = client.select("INBOX", readonly=True)
            if status != "OK":
                raise EmailConnectionError("无法以只读方式打开 INBOX")
        except EmailConnectionError:
            raise
        except (imaplib.IMAP4.error, OSError) as exc:
            raise EmailConnectionError("IMAP 连接或认证失败") from exc
        finally:
            self._close(client)

    def fetch_recent(
        self,
        account: EmailAccount,
        credential: str,
        *,
        previous_uid_validity: int | None,
        last_synced_uid: int | None,
        limit: int,
        max_message_bytes: int,
    ) -> tuple[int, list[RemoteEmail]]:
        client = self._connect(account)
        try:
            client.login(account.email_address, credential)
            self._identify_client(client, account)
            status, _ = client.select("INBOX", readonly=True)
            if status != "OK":
                raise EmailConnectionError("无法以只读方式打开 INBOX")
            uid_validity = self._uid_validity(client)
            minimum_uid = (last_synced_uid or 0) + 1 if previous_uid_validity == uid_validity else 1
            status, data = client.uid("search", None, "ALL")
            if status != "OK":
                raise EmailConnectionError("无法读取 INBOX 邮件 UID")
            uid_values = [
                int(value) for value in (data[0] or b"").split() if int(value) >= minimum_uid
            ][-limit:]
            messages = [self._fetch_one(client, uid, max_message_bytes) for uid in uid_values]
            return uid_validity, messages
        except EmailConnectionError:
            raise
        except (imaplib.IMAP4.error, OSError, ValueError) as exc:
            raise EmailConnectionError("IMAP 同步失败") from exc
        finally:
            self._close(client)

    def fetch_raw_message(
        self,
        account: EmailAccount,
        credential: str,
        *,
        folder: str,
        uid: int,
        max_message_bytes: int,
    ) -> bytes:
        client = self._connect(account)
        try:
            client.login(account.email_address, credential)
            self._identify_client(client, account)
            status, _ = client.select(folder, readonly=True)
            if status != "OK":
                raise EmailConnectionError("无法以只读方式打开邮件文件夹")
            remote = self._fetch_one(client, uid, max_message_bytes)
            if remote.truncated:
                raise EmailConnectionError("原邮件超过安全下载上限")
            return remote.raw_message
        except EmailConnectionError:
            raise
        except (imaplib.IMAP4.error, OSError, ValueError) as exc:
            raise EmailConnectionError("IMAP 附件读取失败") from exc
        finally:
            self._close(client)

    def move(
        self,
        account: EmailAccount,
        credential: str,
        *,
        source_folder: str,
        source_uid: int,
        target_folder: str,
        create_target: bool,
        on_copy: Callable[[ImapMoveResult], None] | None = None,
    ) -> ImapMoveResult:
        client = self._connect(account)
        submitted = False
        try:
            client.login(account.email_address, credential)
            self._identify_client(client, account)
            capabilities = {
                (
                    value.decode("ascii", errors="ignore").upper()
                    if isinstance(value, bytes)
                    else str(value).upper()
                )
                for value in getattr(client, "capabilities", ())
            }
            supports_move = "MOVE" in capabilities
            if not supports_move and "UIDPLUS" not in capabilities:
                raise EmailConnectionError(
                    "IMAP 服务器不支持 MOVE 或可检查点恢复的 UIDPLUS"
                )
            if create_target:
                status, _ = client.create(target_folder)
                if status not in {"OK", "NO"}:
                    raise EmailConnectionError("无法创建系统归档文件夹")
            status, _ = client.select(source_folder, readonly=False)
            if status != "OK":
                raise EmailConnectionError("无法以读写方式打开源文件夹")
            submitted = True
            command = "MOVE" if supports_move else "COPY"
            status, _ = client.uid(command, str(source_uid), target_folder)
            if status != "OK":
                raise EmailConnectionError("IMAP 服务器拒绝移动邮件")
            response_status, values = client.response("COPYUID")
            if response_status != "COPYUID" or not values or not values[0]:
                raise ImapMoveUnknownError("IMAP 移动结果无法确认")
            parts = values[0].split()
            if len(parts) < 3:
                raise ImapMoveUnknownError("IMAP 移动结果缺少目标 UID")
            result = ImapMoveResult(
                folder=target_folder,
                uid_validity=int(parts[0]),
                uid=int(parts[2].split(b",")[-1].split(b":")[-1]),
            )
            if supports_move:
                return result
            if on_copy is None:
                raise ImapMoveUnknownError("IMAP 复制成功，但缺少持久化检查点")
            try:
                on_copy(result)
            except Exception as exc:
                raise ImapMoveUnknownError(
                    "IMAP 复制成功，但检查点持久化失败"
                ) from exc
            status, _ = client.uid(
                "STORE",
                str(source_uid),
                "+FLAGS.SILENT",
                r"(\Deleted)",
            )
            if status != "OK":
                raise ImapMoveUnknownError("IMAP 复制成功，但源邮件删除结果不明确")
            status, _ = client.uid("EXPUNGE", str(source_uid))
            if status != "OK":
                raise ImapMoveUnknownError("IMAP 复制成功，但源邮件清理结果不明确")
            return result
        except (EmailConnectionError, ImapMoveUnknownError):
            raise
        except (imaplib.IMAP4.error, OSError, UnicodeError, ValueError) as exc:
            if submitted:
                raise ImapMoveUnknownError("IMAP 移动结果无法确认") from exc
            raise EmailConnectionError("IMAP 移动失败") from exc
        finally:
            self._close(client)

    def _connect(self, account: EmailAccount) -> imaplib.IMAP4:
        try:
            if account.imap_security == TransportSecurity.SSL:
                return imaplib.IMAP4_SSL(
                    account.imap_host,
                    account.imap_port,
                    timeout=self._timeout_seconds,
                )
            client = imaplib.IMAP4(
                account.imap_host,
                account.imap_port,
                timeout=self._timeout_seconds,
            )
            client.starttls(ssl_context=ssl.create_default_context())
            return client
        except (imaplib.IMAP4.error, OSError) as exc:
            raise EmailConnectionError("无法连接 IMAP 服务器") from exc

    @staticmethod
    def _uid_validity(client: imaplib.IMAP4) -> int:
        status, values = client.response("UIDVALIDITY")
        if status != "UIDVALIDITY" or not values or not values[0]:
            raise EmailConnectionError("IMAP 服务器未返回 UIDVALIDITY")
        return int(values[0])

    @staticmethod
    def _identify_client(
        client: imaplib.IMAP4,
        account: EmailAccount,
    ) -> None:
        """网易邮箱在登录后、打开文件夹前要求 RFC 2971 客户端标识。"""
        if account.imap_host.lower() not in _NETEASE_IMAP_HOSTS:
            return
        imaplib.Commands.setdefault("ID", ("NONAUTH", "AUTH", "SELECTED"))
        status, _ = client._simple_command("ID", _NETEASE_CLIENT_ID)
        if status != "OK":
            raise EmailConnectionError("IMAP 服务器拒绝客户端标识")

    def _fetch_one(
        self,
        client: imaplib.IMAP4,
        uid: int,
        max_message_bytes: int,
    ) -> RemoteEmail:
        status, size_data = client.uid("fetch", str(uid), "(RFC822.SIZE)")
        if status != "OK":
            raise EmailConnectionError(f"无法读取 UID {uid} 的大小")
        size_metadata = self._metadata(size_data)
        size_match = _SIZE_PATTERN.search(size_metadata)
        message_size = int(size_match.group(1)) if size_match else None
        truncated = message_size is not None and message_size > max_message_bytes
        query = "(BODY.PEEK[HEADER] INTERNALDATE)" if truncated else "(BODY.PEEK[] INTERNALDATE)"
        status, message_data = client.uid("fetch", str(uid), query)
        if status != "OK":
            raise EmailConnectionError(f"无法读取 UID {uid}")
        metadata = self._metadata(message_data)
        return RemoteEmail(
            uid=uid,
            raw_message=self._payload(message_data),
            received_at=self._internal_date(metadata),
            truncated=truncated,
            message_size=message_size,
        )

    @staticmethod
    def _metadata(data: list[bytes | tuple[bytes, bytes]] | None) -> bytes:
        if not data:
            return b""
        return b" ".join(item[0] if isinstance(item, tuple) else item for item in data if item)

    @staticmethod
    def _payload(data: list[bytes | tuple[bytes, bytes]] | None) -> bytes:
        if not data:
            raise EmailConnectionError("IMAP 服务器返回了空邮件")
        for item in data:
            if isinstance(item, tuple) and len(item) > 1:
                return item[1]
        raise EmailConnectionError("IMAP 服务器未返回邮件内容")

    @staticmethod
    def _internal_date(metadata: bytes) -> datetime | None:
        match = _INTERNAL_DATE_PATTERN.search(metadata)
        if not match:
            return None
        try:
            value = parsedate_to_datetime(match.group(1).decode("ascii"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.astimezone(UTC).replace(tzinfo=None)
        except (UnicodeDecodeError, TypeError, ValueError):
            return None

    @staticmethod
    def _close(client: imaplib.IMAP4) -> None:
        try:
            client.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


class SmtpConnectionTester:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    def test_connection(self, account: EmailAccount, credential: str) -> None:
        client: smtplib.SMTP | None = None
        try:
            if account.smtp_security == TransportSecurity.SSL:
                client = smtplib.SMTP_SSL(
                    account.smtp_host,
                    account.smtp_port,
                    timeout=self._timeout_seconds,
                    context=ssl.create_default_context(),
                )
            else:
                client = smtplib.SMTP(
                    account.smtp_host,
                    account.smtp_port,
                    timeout=self._timeout_seconds,
                )
                client.ehlo()
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            client.login(account.email_address, credential)
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailConnectionError("SMTP 连接或认证失败") from exc
        finally:
            if client is not None:
                try:
                    client.quit()
                except (smtplib.SMTPException, OSError):
                    client.close()


class SmtpMailer:
    """只传输已完成格式化的 MIME 邮件，不修改主题或正文。"""

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    def send(
        self,
        account: EmailAccount,
        credential: str,
        message: EmailMessage,
    ) -> str | None:
        client: smtplib.SMTP | None = None
        submitted = False
        try:
            client = self._connect(account)
            client.login(account.email_address, credential)
            submitted = True
            refused = client.send_message(message)
            if refused:
                raise SmtpDeliveryFailedError("SMTP 拒绝了一个或多个收件人")
            return message.get("Message-ID")
        except SmtpDeliveryFailedError:
            raise
        except smtplib.SMTPRecipientsRefused as exc:
            raise SmtpDeliveryFailedError("SMTP 拒绝了全部收件人") from exc
        except (smtplib.SMTPDataError, smtplib.SMTPSenderRefused) as exc:
            raise SmtpDeliveryFailedError("SMTP 明确拒绝邮件") from exc
        except (smtplib.SMTPServerDisconnected, TimeoutError, OSError) as exc:
            if submitted:
                raise SmtpDeliveryUnknownError("SMTP 发送结果无法确认") from exc
            raise SmtpDeliveryFailedError("SMTP 连接或认证失败") from exc
        except smtplib.SMTPException as exc:
            if submitted:
                raise SmtpDeliveryUnknownError("SMTP 发送结果无法确认") from exc
            raise SmtpDeliveryFailedError("SMTP 连接或认证失败") from exc
        finally:
            if client is not None:
                try:
                    client.quit()
                except (smtplib.SMTPException, OSError):
                    client.close()

    def _connect(self, account: EmailAccount) -> smtplib.SMTP:
        if account.smtp_security == TransportSecurity.SSL:
            return smtplib.SMTP_SSL(
                account.smtp_host,
                account.smtp_port,
                timeout=self._timeout_seconds,
                context=ssl.create_default_context(),
            )
        client = smtplib.SMTP(
            account.smtp_host,
            account.smtp_port,
            timeout=self._timeout_seconds,
        )
        client.ehlo()
        client.starttls(context=ssl.create_default_context())
        client.ehlo()
        return client
