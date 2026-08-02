import pytest

from app.infrastructure.security import (
    CredentialNotConfiguredError,
    EncryptedCredentialResolver,
)

TEST_KEY = "11" * 32


def test_authorization_code_is_encrypted_and_can_be_resolved() -> None:
    resolver = EncryptedCredentialResolver(TEST_KEY)

    ciphertext = resolver.protect("authorization-code")

    assert ciphertext.startswith("v1:")
    assert "authorization-code" not in ciphertext
    assert resolver.resolve(ciphertext) == "authorization-code"


def test_ciphertext_cannot_be_decrypted_with_another_key() -> None:
    ciphertext = EncryptedCredentialResolver(TEST_KEY).protect("authorization-code")

    with pytest.raises(CredentialNotConfiguredError, match="重新授权"):
        EncryptedCredentialResolver("22" * 32).resolve(ciphertext)


@pytest.mark.parametrize("ciphertext", [None, "", "OLD_ENV_REFERENCE"])
def test_missing_or_legacy_credential_requires_reauthorization(
    ciphertext: str | None,
) -> None:
    with pytest.raises(CredentialNotConfiguredError, match="重新授权"):
        EncryptedCredentialResolver(TEST_KEY).resolve(ciphertext)


def test_invalid_encryption_key_is_rejected_when_used() -> None:
    resolver = EncryptedCredentialResolver("not-a-key")

    with pytest.raises(CredentialNotConfiguredError, match="十六进制"):
        resolver.protect("authorization-code")


def test_checkpoint_key_is_used_when_email_key_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("JOB_MAIL_CHECKPOINT_ENCRYPTION_KEY", TEST_KEY)
    monkeypatch.delenv("JOB_MAIL_EMAIL_CREDENTIAL_ENCRYPTION_KEY", raising=False)
    try:
        resolver = EncryptedCredentialResolver()
        ciphertext = resolver.protect("authorization-code")
        assert resolver.resolve(ciphertext) == "authorization-code"
    finally:
        get_settings.cache_clear()
