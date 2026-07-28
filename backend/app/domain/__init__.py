"""与框架无关的领域规则和模型。"""

from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    ApplicationStatus,
    ArchiveStatus,
    EmailCategory,
    EmailParseStatus,
    EmailPriority,
    RequiredCapability,
    TransportSecurity,
)

__all__ = [
    "ApplicationSource",
    "ApplicationStage",
    "ApplicationStatus",
    "ArchiveStatus",
    "EmailCategory",
    "EmailParseStatus",
    "EmailPriority",
    "RequiredCapability",
    "TransportSecurity",
]
