import time
import pytest
from hermes_notion import storage

def test_deduplication(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert not storage.is_comment_processed("c100")
    storage.mark_comment_processed("c100")
    assert storage.is_comment_processed("c100")
    assert not storage.is_comment_processed("c101")

def test_circuit_breaker_cooldown(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    discussion_id = "disc_test_1"
    
    # 1. First reply is permitted
    allowed, reason = storage.check_circuit_breaker(discussion_id, cooldown_seconds=2.0)
    assert allowed
    assert reason == "ok"
    
    # Record reply
    storage.record_bot_reply(discussion_id)
    
    # 2. Immediate second reply is blocked by cooldown
    allowed, reason = storage.check_circuit_breaker(discussion_id, cooldown_seconds=2.0)
    assert not allowed
    assert reason == "thread_cooldown_active"

def test_circuit_breaker_velocity(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    discussion_id = "disc_test_velocity"
    
    # Simulate 5 rapid replies
    for _ in range(5):
        storage.record_bot_reply(discussion_id)
        
    # 6th reply trips velocity breaker
    allowed, reason = storage.check_circuit_breaker(
        discussion_id, cooldown_seconds=0.0, max_replies=5, window_seconds=60.0
    )
    assert not allowed
    assert reason == "velocity_breaker_tripped"

def test_circuit_breaker_reset(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    discussion_id = "disc_test_reset"
    
    for _ in range(5):
        storage.record_bot_reply(discussion_id)
        
    storage.check_circuit_breaker(
        discussion_id, cooldown_seconds=0.0, max_replies=5, window_seconds=60.0
    )
    
    # Reset
    storage.reset_circuit_breaker(discussion_id)
    allowed, reason = storage.check_circuit_breaker(discussion_id, cooldown_seconds=0.0, max_replies=5)
    assert allowed
    assert reason == "ok"
