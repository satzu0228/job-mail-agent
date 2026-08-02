import base64

from Crypto.Cipher import AES
from pydantic import SecretStr

from app.core.config import get_settings

_CIPHERTEXT_PREFIX = "v1:"


class CredentialNotConfiguredError(RuntimeError):
    """邮箱授权码或其加密配置不可用。"""


class EncryptedCredentialResolver:
    """使用 AES-GCM 加密邮箱授权码，并只在执行邮件操作时解密。"""

    def __init__(self, encryption_key: SecretStr | str | None = None) -> None:
        settings = get_settings()
        # 可单独配置邮箱密钥；未配置时复用已有 checkpoint 密钥，避免升级后邮箱流程中断。
        self._configured_key = (
            encryption_key
            or settings.email_credential_encryption_key
            or settings.checkpoint_encryption_key
        )

    def protect(self, authorization_code: SecretStr | str) -> str:
        value = (
            authorization_code.get_secret_value()
            if isinstance(authorization_code, SecretStr)
            else authorization_code
        )
        if not value:
            raise CredentialNotConfiguredError("邮箱授权码不能为空")
        cipher = AES.new(_decode_key(self._configured_key), AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(value.encode("utf-8"))
        payload = cipher.nonce + tag + ciphertext
        return _CIPHERTEXT_PREFIX + base64.urlsafe_b64encode(payload).decode("ascii")

    def resolve(self, credential_ciphertext: str | None) -> str:
        if not credential_ciphertext:
            raise CredentialNotConfiguredError("邮箱需要重新授权")
        if not credential_ciphertext.startswith(_CIPHERTEXT_PREFIX):
            raise CredentialNotConfiguredError("邮箱需要重新授权")
        try:
            payload = base64.urlsafe_b64decode(
                credential_ciphertext.removeprefix(_CIPHERTEXT_PREFIX).encode("ascii")
            )
            nonce, tag, ciphertext = payload[:16], payload[16:32], payload[32:]
            cipher = AES.new(
                _decode_key(self._configured_key),
                AES.MODE_GCM,
                nonce=nonce,
            )
            return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise CredentialNotConfiguredError("邮箱授权码无法解密，请重新授权") from exc


def _decode_key(secret: SecretStr | str | None) -> bytes:
    if secret is None:
        raise CredentialNotConfiguredError("服务端尚未配置邮箱凭据加密密钥")
    value = secret.get_secret_value() if isinstance(secret, SecretStr) else secret
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise CredentialNotConfiguredError("邮箱凭据加密密钥必须是十六进制字符串") from exc
    if len(key) not in {16, 24, 32}:
        raise CredentialNotConfiguredError(
            "邮箱凭据加密密钥解码后必须为 16、24 或 32 字节"
        )
    return key
