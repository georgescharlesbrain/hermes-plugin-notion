import asyncio
import hashlib
import hmac
import json
import logging

import pytest
from hermes_notion import adapter, storage
from hermes_notion.settings import NotionSettings


EXPECTED = "11111111-1111-4111-8111-111111111111"
ACTUAL = "22222222-2222-4222-8222-222222222222"
COMMENT = "33333333-3333-4333-8333-333333333333"


class Request:
    path = "/webhooks/notion/greta"

    def __init__(self, integration):
        payload = {"type": "comment.created", "integration_id": integration,
                   "entity": {"type": "comment", "id": COMMENT},
                   "private_payload": "NEVER_LOG_COMMENT_TEXT"}
        self.body = json.dumps(payload).encode()
        self.content_length = len(self.body)
        self.headers = {"X-Notion-Signature": "sha256=" + hmac.new(
            b"NEVER_LOG_SIGNING_SECRET", self.body, hashlib.sha256).hexdigest()}

    async def read(self):
        return self.body


def instance(monkeypatch):
    import hermes_constants
    monkeypatch.setattr(storage, "get_verification_token", lambda *_: None)
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = NotionSettings(profile="greta", bot_integration_id=EXPECTED,
                                 webhook_secret="NEVER_LOG_SIGNING_SECRET")
    obj._home = hermes_constants.get_hermes_home()
    obj._background = set()
    obj._spawn = lambda coro: coro.close()
    return obj


def test_signed_foreign_integration_logs_ids_without_relaxing_gate(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    response = asyncio.run(instance(monkeypatch)._handle_webhook(Request(ACTUAL)))
    assert response.status == 403
    assert "integration mismatch" in caplog.text
    assert EXPECTED in caplog.text and ACTUAL in caplog.text
    assert "NEVER_LOG_SIGNING_SECRET" not in caplog.text
    assert "NEVER_LOG_COMMENT_TEXT" not in caplog.text


@pytest.mark.parametrize("received", [None, {}, "NEVER_LOG_SIGNING_SECRET", "bad\nforged"])
def test_invalid_integration_values_are_redacted(monkeypatch, caplog, received):
    response = asyncio.run(instance(monkeypatch)._handle_webhook(Request(received)))
    assert response.status == 403
    assert "received=<missing-or-invalid>" in caplog.text
    assert "NEVER_LOG_SIGNING_SECRET" not in caplog.text
    assert "forged" not in caplog.text


def test_verified_comment_logs_only_metadata(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    response = asyncio.run(instance(monkeypatch)._handle_webhook(Request(EXPECTED)))
    assert response.status == 200
    assert "Verified comment.created" in caplog.text
    assert COMMENT in caplog.text and EXPECTED in caplog.text
    assert "NEVER_LOG_SIGNING_SECRET" not in caplog.text
    assert "NEVER_LOG_COMMENT_TEXT" not in caplog.text
