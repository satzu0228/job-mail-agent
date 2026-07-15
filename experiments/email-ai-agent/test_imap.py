"""Safely verify IMAP connectivity with the configured test mailbox.

The mailbox is selected read-only and messages are fetched with BODY.PEEK so
this diagnostic does not intentionally change their read/unread state.
"""

from __future__ import annotations

import argparse
import email
import imaplib
import socket
import sys
from email.header import decode_header, make_header
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = WORKSPACE_ROOT / "references" / "Email-AI-Agent"

if not REFERENCE_ROOT.is_dir():
    raise SystemExit(f"未找到参考项目：{REFERENCE_ROOT}")

sys.path.insert(0, str(REFERENCE_ROOT))

from config import (  # noqa: E402
    IMAP_PASSWORD,
    IMAP_PORT,
    IMAP_SERVER,
    IMAP_USERNAME,
)
from core.email_imap import extract_email_body  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读验证测试邮箱的 IMAP 收件功能。")
    parser.add_argument(
        "--subject-contains",
        default="[JobMailAgent IMAP Test]",
        help="用于定位测试邮件的主题片段。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="最多检查最近多少封邮件，默认 10 封。",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="连接和套接字超时秒数，默认 15 秒。",
    )
    return parser.parse_args()


def decode_subject(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeDecodeError):
        return value


def validate_config() -> None:
    missing = [
        name
        for name, value in (
            ("IMAP_USERNAME", IMAP_USERNAME),
            ("IMAP_PASSWORD", IMAP_PASSWORD),
            ("IMAP_SERVER", IMAP_SERVER),
            ("IMAP_PORT", IMAP_PORT),
        )
        if not value
    ]
    if missing:
        raise ValueError(f".env 缺少配置：{', '.join(missing)}")


def identify_client(client: imaplib.IMAP4_SSL) -> None:
    """Send the RFC 2971 client ID required by NetEase IMAP servers."""
    imaplib.Commands.setdefault("ID", ("NONAUTH", "AUTH", "SELECTED"))
    status, data = client._simple_command(
        "ID",
        '("name" "JobMailAgent" "version" "0.1" "vendor" "local-project")',
    )
    if status != "OK":
        reason = data[-1] if data else b"unknown"
        raise imaplib.IMAP4.error(f"IMAP ID failed: {reason!r}")


def main() -> int:
    args = parse_args()
    if args.limit <= 0:
        print("--limit 必须大于 0。", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("--timeout 必须大于 0。", file=sys.stderr)
        return 2

    try:
        validate_config()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    client: imaplib.IMAP4_SSL | None = None
    authenticated = False
    try:
        print(f"正在连接 IMAP：{IMAP_SERVER}:{int(IMAP_PORT)}", flush=True)
        client = imaplib.IMAP4_SSL(
            IMAP_SERVER,
            int(IMAP_PORT),
            timeout=args.timeout,
        )
        print("TLS 连接成功，正在登录……", flush=True)
        client.login(IMAP_USERNAME, IMAP_PASSWORD)
        authenticated = True
        print("IMAP 登录成功，正在发送客户端 ID……", flush=True)
        identify_client(client)
        print("客户端 ID 已接受，正在打开收件箱……", flush=True)

        status, select_data = client.select("INBOX", readonly=True)
        if status != "OK":
            print(
                "服务器不接受 EXAMINE 只读模式，回退到 SELECT INBOX；"
                "后续仍使用 BODY.PEEK，不主动改变已读状态。",
                flush=True,
            )
            status, select_data = client.select("INBOX", readonly=False)
            if status != "OK":
                reason = select_data[-1] if select_data else b"unknown"
                print(f"无法打开 INBOX：{reason!r}", file=sys.stderr)
                return 1

        status, data = client.search(None, "ALL")
        if status != "OK":
            print("无法检索邮件列表。", file=sys.stderr)
            return 1

        message_ids = data[0].split()
        selected_ids = message_ids[-args.limit :]
        print(f"登录成功，收件箱共 {len(message_ids)} 封邮件。")
        print(f"正在检查最近 {len(selected_ids)} 封……")

        matched = False
        for message_id in reversed(selected_ids):
            status, message_data = client.fetch(message_id, "(BODY.PEEK[])")
            if status != "OK" or not message_data or not isinstance(message_data[0], tuple):
                continue

            message = email.message_from_bytes(message_data[0][1])
            subject = decode_subject(message.get("Subject"))
            body = extract_email_body(message) or ""
            print(f"- UID/序号 {message_id.decode()}: {subject}（正文 {len(body)} 字符）")

            if args.subject_contains.lower() in subject.lower():
                matched = True

        if not matched:
            print(
                f"未在最近 {len(selected_ids)} 封邮件中找到主题包含 "
                f"{args.subject_contains!r} 的邮件。",
                file=sys.stderr,
            )
            return 3

        print("IMAP 验证成功：已找到测试邮件，主题和正文均可解析。")
        return 0
    except imaplib.IMAP4.error as exc:
        print(f"IMAP 登录或协议错误：{exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, socket.timeout, TimeoutError) as exc:
        print(f"IMAP 连接错误：{exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            try:
                if authenticated:
                    client.logout()
                else:
                    client.shutdown()
            except (imaplib.IMAP4.error, OSError):
                pass


if __name__ == "__main__":
    raise SystemExit(main())
