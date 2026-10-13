import asyncio
import json
import time
import urllib.parse
import pytest
from hermes_notion import adapter, storage
from hermes_notion.settings import NotionSettings


class Request:
    def __init__(self, payload, path="/webhooks/notion/aroa", headers=None):
        self.body = json.dumps(payload).encode()
        self.content_length = len(self.body)
        query = ""
        if "?" in path:
            path, query = path.split("?", 1)
        self.path = path
        self.query = dict(urllib.parse.parse_qsl(query))
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


def test_handshake_without_our_ticket_binds_a_registered_subscription(monkeypatch, tmp_path):
    """Notion's own verification request carries no ticket id: the operator's
    pre-registered ticket for that (profile, subscription) is the authority."""
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    storage.create_provisioning_ticket(profile="aroa", subscription_id="sub-777", ttl_seconds=300)
    req = Request(
        {"verification_token": "secret-from-notion", "subscription_id": "sub-777"},
        path="/webhooks/notion/aroa",
    )
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 200
    assert storage.get_verification_token("aroa") == "secret-from-notion"


def test_handshake_with_unregistered_subscription_still_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    storage.create_provisioning_ticket(profile="aroa", subscription_id="sub-777", ttl_seconds=300)
    req = Request(
        {"verification_token": "attacker-secret", "subscription_id": "sub-other"},
        path="/webhooks/notion/aroa",
    )
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 403
    assert json.loads(res.text)["error"] == "operator provisioning required"
    assert storage.get_verification_token("aroa") is None


def test_registered_subscription_handshake_is_single_use(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    storage.create_provisioning_ticket(
        profile="aroa", subscription_id="sub-777", ttl_seconds=300, allow_replacement=True
    )
    first = Request(
        {"verification_token": "first-secret", "subscription_id": "sub-777"},
        path="/webhooks/notion/aroa",
    )
    assert asyncio.run(instance("aroa")._handle_webhook(first)).status == 200

    replay = Request(
        {"verification_token": "replay-secret", "subscription_id": "sub-777"},
        path="/webhooks/notion/aroa",
    )
    res = asyncio.run(instance("aroa")._handle_webhook(replay))
    assert res.status == 403
    assert storage.get_verification_token("aroa") == "first-secret"


def test_expired_registered_subscription_ticket_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    storage.create_provisioning_ticket(profile="aroa", subscription_id="sub-777", ttl_seconds=-10)
    req = Request(
        {"verification_token": "late-secret", "subscription_id": "sub-777"},
        path="/webhooks/notion/aroa",
    )
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 403
    assert storage.get_verification_token("aroa") is None


def test_notion_handshake_carries_only_the_token_and_our_ticket_in_the_url(monkeypatch, tmp_path):
    """Notion's real verification POST has one field, verification_token, and no
    subscription id. The operator's ticket rides in the endpoint URL instead."""
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    ticket = storage.create_provisioning_ticket(profile="aroa", subscription_id="", ttl_seconds=3600)
    req = Request(
        {"verification_token": "notion-handshake-token"},
        path=f"/webhooks/notion/aroa?provision_ticket={ticket['ticket_id']}",
    )
    res = asyncio.run(instance("aroa")._handle_webhook(req))
    assert res.status == 200
    assert storage.get_verification_token("aroa") == "notion-handshake-token"


def test_url_ticket_is_single_use(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    ticket = storage.create_provisioning_ticket(
        profile="aroa", subscription_id="", ttl_seconds=3600, allow_replacement=True
    )
    path = f"/webhooks/notion/aroa?provision_ticket={ticket['ticket_id']}"
    first = Request({"verification_token": "first"}, path=path)
    assert asyncio.run(instance("aroa")._handle_webhook(first)).status == 200

    replay = Request({"verification_token": "second"}, path=path)
    res = asyncio.run(instance("aroa")._handle_webhook(replay))
    assert res.status == 403
    assert storage.get_verification_token("aroa") == "first"
