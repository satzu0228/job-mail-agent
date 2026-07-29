from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import SecretStr


class CheckpointConfigurationError(RuntimeError):
    """Checkpoint 路径或加密密钥配置无效。"""


def decode_checkpoint_key(secret: SecretStr | str | None) -> bytes:
    if secret is None:
        raise CheckpointConfigurationError("未配置 checkpoint 加密密钥")
    value = secret.get_secret_value() if isinstance(secret, SecretStr) else secret
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise CheckpointConfigurationError(
            "checkpoint 加密密钥必须是十六进制字符串"
        ) from exc
    if len(key) not in {16, 24, 32}:
        raise CheckpointConfigurationError(
            "checkpoint 加密密钥解码后必须为 16、24 或 32 字节"
        )
    return key


@contextmanager
def sqlite_checkpointer(
    path: Path,
    encryption_key: SecretStr | str | None,
) -> Iterator[SqliteSaver]:
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    serde = EncryptedSerializer.from_pycryptodome_aes(
        serde=JsonPlusSerializer(allowed_msgpack_modules=[]),
        key=decode_checkpoint_key(encryption_key)
    )
    connection = sqlite3.connect(resolved, check_same_thread=False)
    try:
        yield SqliteSaver(connection, serde=serde)
    finally:
        connection.close()
