import argparse
import json
from pathlib import Path
from typing import Any

from app.agents.classification.agent import ClassificationAgent
from app.agents.classification.schemas import ClassificationInput
from app.agents.common.schemas import PreparedEmail
from app.agents.extraction.agent import ExtractionAgent
from app.agents.extraction.schemas import ExtractionInput
from app.core.config import get_settings
from app.infrastructure.llm import LLMConfigurationError, create_chat_model


def analyze_fixture(path: Path) -> dict[str, Any]:
    email = PreparedEmail.model_validate_json(path.read_text(encoding="utf-8"))
    model = create_chat_model(get_settings())

    classification = ClassificationAgent.from_model(model).run(
        ClassificationInput(email=email)
    )
    result: dict[str, Any] = {
        "fixture": str(path),
        "classification": classification.model_dump(mode="json"),
        "extraction": None,
    }
    if classification.is_job_related:
        extraction = ExtractionAgent.from_model(model).run(
            ExtractionInput(email=email, classification=classification)
        )
        result["extraction"] = extraction.model_dump(mode="json")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Classification and Extraction against one anonymized email fixture."
    )
    parser.add_argument("fixture", type=Path, help="Path to a PreparedEmail JSON fixture")
    args = parser.parse_args()
    try:
        result = analyze_fixture(args.fixture)
    except LLMConfigurationError as exc:
        parser.exit(status=2, message=f"配置错误：{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
