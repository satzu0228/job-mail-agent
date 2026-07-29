from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph

from app.infrastructure.checkpoint import (
    CheckpointConfigurationError,
    decode_checkpoint_key,
    sqlite_checkpointer,
)


def test_checkpoint_key_requires_valid_hex_aes_length() -> None:
    assert decode_checkpoint_key("00" * 16) == bytes(16)
    with pytest.raises(CheckpointConfigurationError, match="十六进制"):
        decode_checkpoint_key("not-hex")
    with pytest.raises(CheckpointConfigurationError, match="16、24 或 32"):
        decode_checkpoint_key("00" * 15)


def test_sqlite_checkpoint_encrypts_state_at_rest(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.sqlite"
    builder = StateGraph(dict)
    builder.add_node("identity", lambda state: state)
    builder.add_edge(START, "identity")
    builder.add_edge("identity", END)

    with sqlite_checkpointer(path, "01" * 32) as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        graph.invoke(
            {"secret": "mail-body-plain-text"},
            config={"configurable": {"thread_id": "encrypted-thread"}},
        )

    assert b"mail-body-plain-text" not in path.read_bytes()
