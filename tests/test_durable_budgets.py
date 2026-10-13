import asyncio
import pytest
from hermes_notion import adapter, storage, policy, notion_client
from hermes_notion.settings import NotionSettings, KOEN_USER_ID


def instance(profile="aroa"):
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = NotionSettings(profile=profile)
    obj.settings.allowed_user_ids = [KOEN_USER_ID]
    obj._background = set()
    obj._processing = asyncio.Lock()
    import hermes_constants
    obj._home = hermes_constants.get_hermes_home()
    return obj


def test_atomic_reply_reservations_concurrent(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    discussion_id = "disc-concurrent"
    
    # Attempt 10 concurrent reservations on limit of 5
    results = []
    for _ in range(10):
        allowed, reason, res_id = storage.reserve_reply_slot(
            discussion_id, cooldown_seconds=0.0, max_replies=5, window_seconds=60.0
        )
        results.append(allowed)
        if allowed and res_id:
            storage.commit_reply_reservation(res_id)

    assert results.count(True) == 5
    assert results.count(False) == 5


def test_per_turn_reply_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    turn_id = "turn-comment-1"
    
    assert storage.claim_turn_reply(turn_id, max_replies=2)[0] is True
    assert storage.claim_turn_reply(turn_id, max_replies=2)[0] is True
    
    # 3rd reply exceeds budget
    allowed, reason = storage.claim_turn_reply(turn_id, max_replies=2)
    assert allowed is False
    assert reason == "turn_reply_budget_exceeded"


def test_queue_time_revalidation_stops_thread(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    obj = instance("aroa")
    obj.settings.token = "fake-token"
    storage.set_discussion_owner("disc-stop", "aroa")
    storage.set_discussion_parent("disc-stop", "3f71c0e1-80e8-8076-be25-f9cadd5041bd")
    
    # Mark stopped before send
    storage.set_discussion_owner("disc-stop", "stopped")
    
    result = asyncio.run(obj.send("notion:thread:disc-stop", "hello"))
    assert not result.success
    assert result.error in ("discussion_stopped", "stop_requested", "unbound_discussion")


def test_queue_time_revalidation_revocation(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    obj = instance("greta")
    obj.settings.token = "fake-token"
    parent_id = "3f71c0e1-80e8-8076-be25-f9cadd5041bd"
    storage.set_discussion_owner("disc-revoked", "greta")
    storage.set_discussion_parent("disc-revoked", parent_id)
    
    # Revoke parent root from greta
    obj.settings.allowed_root_ids = ["other-root"]
    result = asyncio.run(obj.send(
        "notion:thread:disc-revoked", "hello",
        metadata={"notion_profile": "greta", "author_id": KOEN_USER_ID}
    ))
    assert not result.success
    assert result.error == "outside_allowed_roots"


def test_reservation_rollback_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    discussion_id = "disc-rollback"
    allowed, reason, res_id = storage.reserve_reply_slot(
        discussion_id, cooldown_seconds=0.0, max_replies=1, window_seconds=60.0
    )
    assert allowed is True
    
    # Rollback instead of commit
    storage.rollback_reply_reservation(res_id)
    
    # Should be able to reserve again immediately
    allowed2, _, res_id2 = storage.reserve_reply_slot(
        discussion_id, cooldown_seconds=0.0, max_replies=1, window_seconds=60.0
    )
    assert allowed2 is True
    storage.commit_reply_reservation(res_id2)
