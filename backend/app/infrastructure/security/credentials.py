import os
import re
from pathlib import Path

from dotenv import dotenv_values

_CREDENTIAL_REF_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_BACKEND_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_ENV_FILES = (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env")


class CredentialNotConfiguredError(RuntimeError):
    """凭据引用无效或没有对应的安全配置。"""


class EnvironmentCredentialResolver:
    """通过数据库中的引用读取环境变量，不持久化邮箱授权码。"""

    def __init__(self, env_files: tuple[Path, ...] | None = None) -> None:
        self._env_files = env_files or _DEFAULT_ENV_FILES

    def resolve(self, credential_ref: str) -> str:
        if not _CREDENTIAL_REF_PATTERN.fullmatch(credential_ref):
            raise CredentialNotConfiguredError("邮箱凭据引用格式无效")
        credential = os.environ.get(credential_ref)
        if not credential:
            for env_file in self._env_files:
                value = dotenv_values(env_file).get(credential_ref)
                if value:
                    credential = value
        if not credential:
            raise CredentialNotConfiguredError("邮箱凭据尚未配置")
        return credential
