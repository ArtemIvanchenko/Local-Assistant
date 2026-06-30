"""Smoke tests for the scaffold — keep CI green from phase 0."""

from local_assistant.config import Settings


def test_owner_ids_parsing():
    s = Settings(owner_chat_ids="111, 222 ,333")
    assert s.owner_ids == [111, 222, 333]


def test_owner_ids_empty():
    assert Settings(owner_chat_ids="").owner_ids == []


def test_defaults_present():
    s = Settings()
    assert s.model_main == "qwen3.5:4b"
    assert s.num_ctx >= 2048
    assert s.working_context_budget <= s.num_ctx
