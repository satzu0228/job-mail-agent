"""分类、抽取、申请匹配与回复生成智能体。"""

from app.agents.classification.schemas import (
    ClassificationInput,
    ClassificationOutput,
)
from app.agents.extraction.schemas import ExtractionInput, ExtractionOutput

__all__ = [
    "ClassificationInput",
    "ClassificationOutput",
    "ExtractionInput",
    "ExtractionOutput",
]
