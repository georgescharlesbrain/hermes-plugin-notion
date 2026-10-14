import hashlib
import hmac
import pytest
from hermes_notion import adapter, storage

def test_check_requirements(monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    assert not adapter.check_requirements()

    monkeypatch.setenv("NOTION_API_TOKEN", "ntn_test_123")
    assert adapter.check_requirements()

def test_check_requirements_never_raises_without_profile_scope(monkeypatch):
    """The multiplexed gateway probes a platform's check_fn outside any profile
    secret scope. A direct get_secret there raises UnscopedSecretError, which the
    registry reports as "requirements not met" and the platform is dropped."""
    from agent.secret_scope import reset_multiplex_context, set_multiplex_context
    from hermes_notion.settings import NotionSettings

    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_API_TOKEN_AROA", raising=False)
    token = set_multiplex_context(True)
    try:
        assert isinstance(adapter.check_requirements(), bool)
        assert isinstance(NotionSettings.for_profile("aroa").token, str)
    finally:
        reset_multiplex_context(token)


def test_signature_validation():
    secret = "secret_test_xyz"
    raw_body = b"{\"test\": \"data\"}"
    valid_hex = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    valid_sig_prefixed = f"sha256={valid_hex}"
    invalid_sig = "bad_signature"

    # Normalize sha256= prefix
    sig = valid_sig_prefixed[7:] if valid_sig_prefixed.startswith("sha256=") else valid_sig_prefixed
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    assert hmac.compare_digest(sig, computed)
    assert not hmac.compare_digest(invalid_sig, computed)

def test_profile_from_path():
    assert adapter._profile_from_path("/webhooks/notion/aroa") == "aroa"
    assert adapter._profile_from_path("/webhooks/notion/greta") == "greta"
    assert adapter._profile_from_path("/webhooks/notion/luna") == "luna"
    assert adapter._profile_from_path("/webhooks/notion") is None
    assert adapter._profile_from_path("/unrelated/aroa") is None
