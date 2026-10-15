"""输出状态重构前的只读数据一致性审计报告。"""

from __future__ import annotations

import argparse
import json
import sys

from app.application.state_audit import DEFAULT_SAMPLE_LIMIT, StateAuditService
from app.infrastructure.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读审计业务状态一致性")
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=DEFAULT_SAMPLE_LIMIT,
        help="每类异常最多输出的样例 ID 数量",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with SessionLocal() as session:
        try:
            report = StateAuditService(session).run(sample_limit=args.sample_limit)
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        finally:
            session.rollback()


if __name__ == "__main__":
    main()
