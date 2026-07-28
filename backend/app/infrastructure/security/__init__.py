"""凭据引用与敏感数据保护适配器。"""

from app.infrastructure.security.credentials import (
    CredentialNotConfiguredError,
    EnvironmentCredentialResolver,
)

__all__ = ["CredentialNotConfiguredError", "EnvironmentCredentialResolver"]
