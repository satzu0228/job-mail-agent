"""Send one fixed SMTP test message from the configured mailbox to itself."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = WORKSPACE_ROOT / "references" / "Email-AI-Agent"

if not REFERENCE_ROOT.is_dir():
    raise SystemExit(f"未找到参考项目：{REFERENCE_ROOT}")

sys.path.insert(0, str(REFERENCE_ROOT))

from config import (  # noqa: E402
    EMAIL_PASSWORD,
    EMAIL_PORT,
    EMAIL_SERVER,
    EMAIL_USERNAME,
)
from core.email_sender import send_email  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="向当前测试邮箱自身发送一封 SMTP 测试邮件。")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="明确确认发送；未提供该参数时不会连接 SMTP。",
    )
    return parser.parse_args()


def validate_config() -> list[str]:
    return [
        name
        for name, value in (
            ("EMAIL_USERNAME", EMAIL_USERNAME),
            ("EMAIL_PASSWORD", EMAIL_PASSWORD),
            ("EMAIL_SERVER", EMAIL_SERVER),
            ("EMAIL_PORT", EMAIL_PORT),
        )
        if not value
    ]


def main() -> int:
    args = parse_args()
    missing = validate_config()
    if missing:
        print(f".env 缺少配置：{', '.join(missing)}", file=sys.stderr)
        return 2

    print(f"SMTP 服务器：{EMAIL_SERVER}:{EMAIL_PORT}")
    print("发送方式：测试邮箱自发自收")
    print("主题：[JobMailAgent SMTP Test] 自发自收测试")

    if not args.confirm:
        print("未提供 --confirm，没有发送邮件。")
        return 0

    test_email = {
        "from": EMAIL_USERNAME,
        "subject": "[JobMailAgent SMTP Test] 自发自收测试",
        "response": (
            "这是一封由 Email-AI-Agent 通过 SMTP 发送的测试邮件。"
            "收到此邮件表示 SMTP SSL、身份认证和发送链路工作正常。"
        ),
    }

    if not send_email(test_email, "JobMailAgent 测试"):
        print("SMTP 测试失败，请查看上方错误日志。", file=sys.stderr)
        return 1

    print("SMTP 服务器已接受测试邮件，请前往 163 收件箱确认是否收到。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

