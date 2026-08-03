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
    settings = get_settings()
    if settings.llm_api_key is None:
        raise LLMConfigurationError(
            "CLI 工具需要通过 JOB_MAIL_LLM_API_KEY 或 DEEPSEEK_API_KEY 环境变量提供 API Key"
        )
    llm_config = {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "api_key": settings.llm_api_key.get_secret_value(),
        "base_url": None,
        "temperature": settings.llm_temperature,
        "timeout_seconds": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }
    model = create_chat_model(settings, llm_config)

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
