"""导出确定排序的 OpenAPI 契约基线。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出当前 FastAPI OpenAPI 契约")
    parser.add_argument("output", type=Path, help="输出 JSON 文件路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
