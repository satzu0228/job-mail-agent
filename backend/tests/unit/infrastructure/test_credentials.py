from pathlib import Path

import pytest

from app.infrastructure.security import (
    CredentialNotConfiguredError,
    EnvironmentCredentialResolver,
)


def test_environment_credential_resolver_uses_reference_without_echoing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOB_MAIL_EMAIL_CREDENTIAL_TEST", "authorization-code")

    value = EnvironmentCredentialResolver().resolve("JOB_MAIL_EMAIL_CREDENTIAL_TEST")

    assert value == "authorization-code"


def test_environment_credential_resolver_reads_configured_env_file(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "JOB_MAIL_EMAIL_CREDENTIAL_FILE=authorization-code\n",
        encoding="utf-8",
    )

    value = EnvironmentCredentialResolver((env_file,)).resolve("JOB_MAIL_EMAIL_CREDENTIAL_FILE")

    assert value == "authorization-code"


@pytest.mark.parametrize("reference", ["lowercase", "../SECRET", "A"])
def test_environment_credential_resolver_rejects_unsafe_reference(
    reference: str,
) -> None:
    with pytest.raises(CredentialNotConfiguredError):
        EnvironmentCredentialResolver().resolve(reference)
