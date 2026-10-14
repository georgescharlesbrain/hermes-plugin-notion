import asyncio
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from hermes_notion import adapter, notion_client, storage
from hermes_notion.settings import NotionSettings


def test_inbound_probe_does_not_block_immediate_reply():
    storage.set_discussion_owner("discussion", "aroa")
    storage.set_discussion_parent("discussion", "root")
    assert storage.check_circuit_breaker("discussion")[0]
    allowed, reason, reservation = storage.reserve_reply_slot("discussion")
    assert allowed, reason
    storage.commit_reply_reservation(reservation)


def test_dispatch_posts_one_reply_without_consuming_cooldown(monkeypatch):
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = NotionSettings(profile="aroa", token="fixture", allowed_user_ids=["human"], allowed_root_ids=["root"])
    import hermes_constants
    obj._home = hermes_constants.get_hermes_home()
    obj._processing = asyncio.Lock()
    obj.build_source = lambda **kw: SimpleNamespace(**kw)
    comment = {"id": "comment", "discussion_id": "discussion", "parent": {"page_id": "root"},
               "created_by": {"id": "human", "type": "person"},
               "rich_text": [{"type": "text", "plain_text": "@aroa ping"}]}
    calls = []
    monkeypatch.setattr(notion_client, "get_comment", lambda token, cid:
                        comment if cid == "comment" else {"id": cid, "discussion_id": "discussion"})
    def post(**kw):
        calls.append(kw)
        return {"id": "reply"}
    monkeypatch.setattr(notion_client, "create_acknowledgement", post)
    async def handle(event):
        assert event.metadata["author_id"] == "human"
        result = await obj.send(event.source.chat_id, "pong", metadata=event.metadata)
        assert result.success, result.error
    obj.handle_message = handle
    asyncio.run(obj._process_comment_id("comment", "aroa"))
    assert len(calls) == 1
    assert storage.is_comment_processed("comment")


def test_budget_and_stop_survive_process_restart(tmp_path):
    script = """
import sys
from hermes_notion import storage
if sys.argv[1] == "first":
    storage.set_discussion_owner("discussion", "aroa")
    storage.set_discussion_parent("discussion", "root")
    assert storage.claim_comment("comment")
    assert storage.claim_turn_reply("comment", 1)[0]
    allowed, reason, reservation = storage.reserve_reply_slot("discussion")
    assert allowed, reason
    storage.commit_reply_reservation(reservation)
    storage.set_discussion_owner("stopped", "stopped")
else:
    assert storage.get_discussion_owner("discussion") == "aroa"
    assert storage.get_discussion_parent("discussion") == "root"
    assert not storage.claim_comment("comment")
    assert not storage.claim_turn_reply("comment", 1)[0]
    assert storage.reserve_reply_slot("discussion")[1] == "thread_cooldown_active"
    assert storage.reserve_reply_slot("stopped")[1] == "discussion_stopped"
"""
    from pathlib import Path
    env = {**os.environ, "HERMES_HOME": str(tmp_path),
           "PYTHONPATH": str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    for phase in ("first", "second"):
        result = subprocess.run([sys.executable, "-c", script, phase], env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr


def test_gateway_reply_anchor_restores_human_and_turn_budget(monkeypatch):
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = NotionSettings(profile="aroa", token="fixture", allowed_user_ids=["human"], allowed_root_ids=["root"])
    import hermes_constants
    obj._home = hermes_constants.get_hermes_home()
    storage.set_discussion_owner("discussion", "aroa")
    storage.set_discussion_parent("discussion", "root")
    writes = []
    monkeypatch.setattr(notion_client, "get_comment", lambda token, cid:
                        {"id": cid, "discussion_id": "discussion", "created_by": {"id": "human"}})
    def post(**kw):
        writes.append(kw)
        return {"id": "reply"}
    monkeypatch.setattr(notion_client, "create_comment_reply", post)
    result = asyncio.run(obj.send("notion:thread:discussion", "pong", reply_to="original", metadata={"thread_id": "discussion"}))
    assert result.success, result.error
    assert storage.claim_turn_reply("original", 1)[1] == "turn_reply_budget_exceeded"
    assert len(writes) == 1


def test_gateway_reply_anchor_denies_revoked_author(monkeypatch):
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = NotionSettings(profile="aroa", token="fixture", allowed_user_ids=["human"], allowed_root_ids=["root"])
    import hermes_constants
    obj._home = hermes_constants.get_hermes_home()
    storage.set_discussion_owner("discussion", "aroa")
    storage.set_discussion_parent("discussion", "root")
    monkeypatch.setattr(notion_client, "get_comment", lambda token, cid:
                        {"id": cid, "discussion_id": "discussion", "created_by": {"id": "revoked"}})
    monkeypatch.setattr(notion_client, "create_comment_reply", lambda **kw: pytest.fail("must not write"))
    result = asyncio.run(obj.send("notion:thread:discussion", "pong", reply_to="original"))
    assert result.error == "unauthorized_human_issuer"


def test_failed_readback_never_reposts_through_gateway(monkeypatch):
    from gateway.platforms.base import SendResult
    obj = object.__new__(adapter.NotionAdapter)
    obj.platform = SimpleNamespace(value="notion")
    attempts = []
    async def send(**kw):
        attempts.append(kw)
        return SendResult(success=False, error="reply_readback_mismatch")
    monkeypatch.setattr(obj, "send", send)
    result = asyncio.run(obj._send_with_retry("discussion", "pong"))
    assert not result.success
    assert len(attempts) == 1


def test_reply_reservations_are_atomic_under_actual_concurrency(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    storage.set_discussion_owner("discussion", "aroa")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: storage.reserve_reply_slot("discussion", 0.0, 5, 60.0), range(20)))
    assert sum(result[0] for result in results) == 5


def test_per_turn_budget_is_atomic_under_actual_concurrency(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    storage.set_discussion_owner("discussion", "aroa")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: storage.claim_turn_reply("turn", 2), range(20)))
    assert sum(result[0] for result in results) == 2
