import hashlib
import hmac
import json
import pytest
from hermes_notion import adapter, storage
from hermes_notion.settings import NotionSettings

def test_check_requirements(monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    assert not adapter.check_requirements()

    monkeypatch.setenv("NOTION_API_TOKEN", "ntn_test_123")
    assert adapter.check_requirements()

def test_signature_validation():
    secret = "secret_test_xyz"
    raw_body = b"{\"test\": \"data\"}"
    valid_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    invalid_sig = "bad_signature"

    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    assert hmac.compare_digest(valid_sig, computed)
    assert not hmac.compare_digest(invalid_sig, computed)
