"""Run the Email-AI-Agent LangGraph workflow with local sample emails only.

This experiment deliberately avoids IMAP and SMTP. It imports the reference
project in place so that compatibility changes remain small and easy to audit.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = WORKSPACE_ROOT / "references" / "Email-AI-Agent"

if not REFERENCE_ROOT.is_dir():
    raise SystemExit(
        "Email-AI-Agent was not found. Expected it at: "
        f"{REFERENCE_ROOT}"
    )

sys.path.insert(0, str(REFERENCE_ROOT))

from config import DEEPSEEK_API_KEY  # noqa: E402
from core.email_ingestion import fetch_email  # noqa: E402
from core.state import EmailState  # noqa: E402
from core.supervisor import supervisor_langgraph  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Email-AI-Agent with sample_emails.json (no IMAP/SMTP)."
    )
    parser.add_argument(
        "--your-name",
        default="求职者",
        help="Name used in the generated reply signature.",
    )
    parser.add_argument(
        "--recipient-name",
        default="招聘负责人",
        help="Name used in the generated reply greeting.",
    )
    parser.add_argument(
        "--email-index",
        type=int,
        default=0,
        help="Zero-based index of the sample email to process.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not DEEPSEEK_API_KEY:
        print(
            "缺少 DEEPSEEK_API_KEY。请创建 references/Email-AI-Agent/.env，"
            "并添加 DEEPSEEK_API_KEY=<你的密钥>。",
            file=sys.stderr,
        )
        return 2

    emails = fetch_email(simulate=True)
    if not emails:
        print("没有加载到模拟邮件。", file=sys.stderr)
        return 1

    if not 0 <= args.email_index < len(emails):
        print(
            f"无效的 --email-index {args.email_index}；可用范围为 "
            f"0..{len(emails) - 1}。",
            file=sys.stderr,
        )
        return 2

    selected_email = emails[args.email_index]
    state = EmailState(
        emails=[selected_email],
        current_email=selected_email,
    )

    print("正在通过 LangGraph 处理本地模拟邮件……")
    print(f"主题：{selected_email.get('subject', '')}")
    print("IMAP：已禁用 | SMTP：已禁用")

    final_state = supervisor_langgraph(
        selected_email,
        state,
        args.your_name,
        args.recipient_name,
    )

    result = final_state["current_email"] if isinstance(final_state, dict) else final_state.current_email
    print("\n=== 处理结果 ===")
    print(f"分类：{result.get('classification', '')}")
    print(f"摘要：{result.get('summary', '')}")
    print("回复草稿：")
    print(result.get("response", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
