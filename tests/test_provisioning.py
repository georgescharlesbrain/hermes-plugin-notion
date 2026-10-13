import asyncio
import json
import time
import pytest
from hermes_notion import adapter, storage
from hermes_notion.settings import NotionSettings


class Request:
    def __init__(self, payload, path="/webhooks/notion/aroa", headers=None):
        self.body = json.dumps(payload).encode()
        self.content_length = len(self.body)
        self.path = path
        self.headers = headers or {}

    async def read(self):
        return self.body


def instance(profile="aroa"):
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = NotionSettings(profile=profile)
    obj._background = set()
    obj._processing = asyncio.Lock()
    import hermes_constants
    obj._home = hermes_constants.get_hermes_home()
    return obj


def test_unauthenticated_handshake_rejected():
    req = Request({"verification_token": "unauth-secret"})
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 403
    data = json.loads(res.text)
    assert data["error"] == "operator provisioning required"


def test_authenticated_provisioning_success(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    ticket = storage.create_provisioning_ticket(
        profile="aroa",
        subscription_id="sub-123",
        ttl_seconds=300,
    )
    payload = {
        "verification_token": "verified-secret-456",
        "subscription_id": "sub-123",
        "provision_ticket": ticket["ticket_id"],
    }
    req = Request(payload, path="/webhooks/notion/aroa")
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 200
    assert storage.get_verification_token("aroa") == "verified-secret-456"


def test_provisioning_ticket_expiry(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    ticket = storage.create_provisioning_ticket(
        profile="aroa",
        subscription_id="sub-123",
        ttl_seconds=-10,  # expired
    )
    payload = {
        "verification_token": "expired-secret",
        "subscription_id": "sub-123",
        "provision_ticket": ticket["ticket_id"],
    }
    req = Request(payload, path="/webhooks/notion/aroa")
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 403
    assert "expired" in json.loads(res.text)["error"].lower()
    assert storage.get_verification_token("aroa") != "expired-secret"


def test_provisioning_ticket_replay_denied(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    ticket = storage.create_provisioning_ticket(
        profile="aroa",
        subscription_id="sub-123",
        ttl_seconds=300,
    )
    payload = {
        "verification_token": "secret-1",
        "subscription_id": "sub-123",
        "provision_ticket": ticket["ticket_id"],
    }
    req1 = Request(payload, path="/webhooks/notion/aroa")
    res1 = asyncio.run(instance("aroa")._handle_webhook(req1))
    assert res1.status == 200

    # Replay same ticket
    payload["verification_token"] = "secret-2"
    req2 = Request(payload, path="/webhooks/notion/aroa")
    res2 = asyncio.run(instance("aroa")._handle_webhook(req2))
    assert res2.status == 403
    assert "consumed" in json.loads(res2.text)["error"].lower()
    assert storage.get_verification_token("aroa") == "secret-1"


def test_provisioning_wrong_profile_denied(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    ticket = storage.create_provisioning_ticket(
        profile="greta",
        subscription_id="sub-123",
        ttl_seconds=300,
    )
    payload = {
        "verification_token": "secret-for-greta",
        "subscription_id": "sub-123",
        "provision_ticket": ticket["ticket_id"],
    }
    req = Request(payload, path="/webhooks/notion/aroa")
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 403
    assert "mismatch" in json.loads(res.text)["error"].lower()


def test_provisioning_replacement_denied(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    storage.save_verification_token("initial-valid-secret", profile="aroa")

    # Ticket created without allow_replacement=True
    ticket = storage.create_provisioning_ticket(
        profile="aroa",
        subscription_id="sub-123",
        ttl_seconds=300,
        allow_replacement=False,
    )
    payload = {
        "verification_token": "unauthorized-replacement",
        "subscription_id": "sub-123",
        "provision_ticket": ticket["ticket_id"],
    }
    req = Request(payload, path="/webhooks/notion/aroa")
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 403
    assert "replacement" in json.loads(res.text)["error"].lower()
    assert storage.get_verification_token("aroa") == "initial-valid-secret"
