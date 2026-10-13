import pytest
from hermes_notion import policy, notion_client

VALID_UUID_1 = "3f71c0e1-80e8-8106-9516-fb873d6e5ade"
VALID_UUID_1_NO_DASH = "3f71c0e180e881069516fb873d6e5ade"
VALID_UUID_2 = "4c91c0e1-80e8-82cd-af18-87e2c3c7840e"
VALID_UUID_3 = "3f71c0e1-80e8-8076-be25-f9cadd5041bd"

def test_strict_identifier_validation():
    assert policy.is_strict_notion_id(VALID_UUID_1)
    assert policy.is_strict_notion_id(VALID_UUID_1_NO_DASH)
    assert policy.is_strict_notion_id(VALID_UUID_1.upper())
    
    # Malformed identifiers
    assert not policy.is_strict_notion_id("")
    assert not policy.is_strict_notion_id(None)
    assert not policy.is_strict_notion_id(12345)
    assert not policy.is_strict_notion_id("3f71c0e1-80e8-8106-9516-fb873d6e5adg")  # invalid hex 'g'
    assert not policy.is_strict_notion_id("3f71c0e1-80e8-8106-9516-fb873d6e5ad")   # too short
    assert not policy.is_strict_notion_id("../etc/passwd")
    assert not policy.is_strict_notion_id("3f71c0e1-80e8-8106-9516-fb873d6e5ade; DROP TABLE")

def test_modern_ancestry_data_source_parent(monkeypatch):
    objects = {
        VALID_UUID_1: {"parent": {"type": "data_source_id", "data_source_id": VALID_UUID_2}},
        VALID_UUID_2: {"parent": {"type": "database_id", "database_id": VALID_UUID_3}},
    }
    monkeypatch.setattr(notion_client, "get_block", lambda t, i: objects[i])
    assert policy.in_scope("token", VALID_UUID_1, [VALID_UUID_3])
    assert policy.in_scope("token", VALID_UUID_1_NO_DASH, [VALID_UUID_3])

def test_modern_ancestry_database_parent(monkeypatch):
    objects = {
        VALID_UUID_1: {"parent": {"type": "database_id", "database_id": VALID_UUID_3}},
    }
    monkeypatch.setattr(notion_client, "get_block", lambda t, i: objects[i])
    assert policy.in_scope("token", VALID_UUID_1, [VALID_UUID_3])

def test_modern_ancestry_workspace_parent(monkeypatch):
    objects = {
        VALID_UUID_1: {"parent": {"type": "workspace", "workspace": True}},
    }
    monkeypatch.setattr(notion_client, "get_block", lambda t, i: objects[i])
    assert not policy.in_scope("token", VALID_UUID_1, [VALID_UUID_3])
    assert policy.in_scope("token", VALID_UUID_1, ["workspace"])

def test_unknown_parent_type_fails_closed(monkeypatch):
    objects = {
        VALID_UUID_1: {"parent": {"type": "unsupported_future_container", "unsupported_future_container": VALID_UUID_3}},
    }
    monkeypatch.setattr(notion_client, "get_block", lambda t, i: objects[i])
    assert not policy.in_scope("token", VALID_UUID_1, [VALID_UUID_3])

def test_malformed_identifier_fails_closed(monkeypatch):
    assert not policy.in_scope("token", "../bad-id", [VALID_UUID_3])
    assert not policy.in_scope("token", VALID_UUID_1, ["../bad-root"])
    
    objects = {
        VALID_UUID_1: {"parent": {"type": "page_id", "page_id": "../escape-root"}},
    }
    monkeypatch.setattr(notion_client, "get_block", lambda t, i: objects[i])
    assert not policy.in_scope("token", VALID_UUID_1, [VALID_UUID_3])
