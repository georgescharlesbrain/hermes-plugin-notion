import asyncio
import json
from types import SimpleNamespace

import pytest
from hermes_notion import adapter, router, storage
from hermes_notion.settings import NotionSettings


def test_display_name_never_grants_authority():
    comment = {"created_by": {"id": "attacker", "name": "Koen"},
               "display_name": {"resolved_name": "GCB"}}
    assert not router.is_author_authorized(comment, "aroa")


def test_unknown_profile_never_inherits_greta(monkeypatch):
    monkeypatch.setenv("NOTION_API_TOKEN", "fake-launch-token")
    with pytest.raises(ValueError):
        NotionSettings.for_profile("unknown")


class Request:
    path = "/webhooks/notion/greta"
    headers = {}
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()
        self.content_length = len(self.body)
    async def read(self):
        return self.body


def instance():
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = NotionSettings(profile="greta")
    obj._background = set()
    obj.build_source = lambda **kw: SimpleNamespace(**kw)
    obj._processing = asyncio.Lock()
    import hermes_constants
    obj._home = hermes_constants.get_hermes_home()
    return obj


def test_unsigned_ingress_fails_closed(monkeypatch):
    monkeypatch.setattr(storage, "get_verification_token", lambda *a: None)
    response = asyncio.run(instance()._handle_webhook(Request({"type": "comment.created"})))
    assert response.status == 503


def test_handshake_cannot_overwrite_secret(monkeypatch):
    writes = []
    monkeypatch.setattr(storage, "save_verification_token", lambda *a: writes.append(a))
    response = asyncio.run(instance()._handle_webhook(Request({"verification_token": "attacker-secret"})))
    assert response.status == 403
    assert not writes


def test_foreign_profile_ingress_rejected():
    request = Request({})
    request.path = "/webhooks/notion/aroa"
    assert asyncio.run(instance()._handle_webhook(request)).status == 404


def test_storage_uses_context_home(tmp_path, monkeypatch):
    import hermes_constants
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "launch"))
    token = hermes_constants.set_hermes_home_override(str(tmp_path / "served"))
    try:
        assert storage.data_dir() == tmp_path / "served" / "plugin-data" / "notion"
    finally:
        hermes_constants.reset_hermes_home_override(token)


def test_secret_resolution_is_scope_aware(monkeypatch):
    from agent.secret_scope import set_secret_scope, reset_secret_scope, set_multiplex_context, reset_multiplex_context
    monkeypatch.setenv("NOTION_API_TOKEN", "fake-launch")
    scope = set_secret_scope({"NOTION_API_TOKEN": "fake-served"})
    multi = set_multiplex_context(True)
    try:
        assert NotionSettings.for_profile("greta").token == "fake-served"
    finally:
        reset_secret_scope(scope)
        reset_multiplex_context(multi)


def human_comment(text, **kwargs):
    return {"id": "c1", "discussion_id": "d1", "parent": {"page_id": "root"},
            "created_by": {"id": "human", "type": "person"},
            "rich_text": [{"type": "text", "plain_text": text}], **kwargs}


def test_true_mentions_match_ids_not_display_names():
    settings = NotionSettings(profile="greta", bot_user_id="real-bot", allowed_user_ids=["human"])
    comment = human_comment("@greta help", rich_text=[{
        "type": "mention", "plain_text": "@greta help",
        "mention": {"type": "user", "user": {"id": "other", "name": "greta"}}}])
    assert not router.evaluate_comment(comment, settings).actionable


def test_stop_closes_owned_thread():
    settings = NotionSettings(profile="greta", allowed_user_ids=["human"])
    routed = router.evaluate_comment(human_comment("@greta stop"), settings, "greta")
    assert not routed.actionable
    assert routed.reason == "stop_requested"


def test_missing_ids_cannot_dispatch():
    settings = NotionSettings(profile="greta", allowed_user_ids=["human"])
    assert not router.evaluate_comment(human_comment("@greta help", discussion_id=""), settings).actionable


def test_scope_denies_unconfigured_roots():
    from hermes_notion import policy
    assert not policy.in_scope("fake-token", "root", [])


def test_scope_checks_ancestry_and_cycles(monkeypatch):
    from hermes_notion import policy, notion_client
    objects = {"child": {"parent": {"type": "page_id", "page_id": "root"}},
               "loop": {"parent": {"type": "block_id", "block_id": "loop"}}}
    monkeypatch.setattr(notion_client, "get_block", lambda t, i: objects[i])
    assert policy.in_scope("fake-token", "child", ["root"])
    assert not policy.in_scope("fake-token", "loop", ["root"])


def test_reply_tool_denies_unbound_thread(monkeypatch):
    from hermes_notion import tools, notion_client
    monkeypatch.setattr(tools, "_load_token", lambda: "fake-token")
    writes = []
    monkeypatch.setattr(notion_client, "create_comment_reply", lambda *a: writes.append(a))
    assert not tools.reply_comment({"discussion_id": "unbound", "content": "hello"})["ok"]
    assert not writes


def test_adapter_dispatch_reuses_discussion_and_deduplicates(monkeypatch):
    from hermes_notion import notion_client
    obj = instance()
    obj.settings.token = "fake-token"
    obj.settings.allowed_user_ids = ["human"]
    obj.settings.allowed_root_ids = ["root"]
    received = []
    async def handle(event):
        received.append(event)
    obj.handle_message = handle
    monkeypatch.setattr(notion_client, "get_comment", lambda *a: human_comment("@greta explain"))
    async def run():
        await asyncio.gather(obj._process_comment_id("c1", "greta"), obj._process_comment_id("c1", "greta"))
    asyncio.run(run())
    assert len(received) == 1
    assert received[0].source.chat_id == "notion:thread:d1"
    assert received[0].source.profile == "greta"
    assert not received[0].allow_gateway_control


def test_adapter_uses_owning_home_when_callback_context_differs(tmp_path):
    import hermes_constants
    obj = instance()
    owner = obj._home
    token = hermes_constants.set_hermes_home_override(str(tmp_path / "foreign"))
    try:
        observed = []
        async def inner(c, p):
            observed.append(hermes_constants.get_hermes_home())
        obj._process_comment_serial = inner
        asyncio.run(obj._process_comment_id("c1", "greta"))
        assert observed == [owner]
    finally:
        hermes_constants.reset_hermes_home_override(token)


@pytest.mark.parametrize("mode, expected", [("valid", 200), ("invalid", 401), ("missing", 401)])
def test_actual_webhook_signature_handler(mode, expected):
    import hmac, hashlib
    obj = instance()
    obj.settings.webhook_secret = "fake-signing-secret"
    req = Request({"type": "comment.created", "entity": {"type": "comment", "id": "c1"}})
    req.headers = {}
    if mode != "missing":
        digest = hmac.new(b"fake-signing-secret", req.body, hashlib.sha256).hexdigest()
        req.headers["X-Notion-Signature"] = "sha256=" + (digest if mode == "valid" else "bad")
    spawned = []
    def spawn(coro):
        spawned.append(coro)
        coro.close()
    obj._spawn = spawn
    response = asyncio.run(obj._handle_webhook(req))
    assert response.status == expected
    assert len(spawned) == (1 if mode == "valid" else 0)


def test_reply_checks_exact_target_readback(monkeypatch):
    from hermes_notion import notion_client
    obj = instance()
    obj.settings.token = "fake-token"
    obj.settings.allowed_root_ids = ["root"]
    storage.set_discussion_owner("d1", "greta")
    storage.set_discussion_parent("d1", "root")
    calls = []
    def post(**kw):
        calls.append(("post", kw["discussion_id"], kw["token"]))
        return {"id": "reply"}
    def read(token, cid):
        calls.append(("read", cid, token))
        return {"id": cid, "discussion_id": "d1"}
    monkeypatch.setattr(notion_client, "create_comment_reply", post)
    monkeypatch.setattr(notion_client, "get_comment", read)
    result = asyncio.run(obj.send("notion:thread:d1", "hello"))
    assert result.success
    assert calls == [("post", "d1", "fake-token"), ("read", "reply", "fake-token")]


def test_reply_rejects_foreign_profile_before_api(monkeypatch):
    from hermes_notion import notion_client
    monkeypatch.setattr(notion_client, "create_comment_reply", lambda **kw: pytest.fail("must not post"))
    result = asyncio.run(instance().send("notion:thread:d1", "hello", metadata={"notion_profile": "aroa"}))
    assert not result.success
    assert result.error == "profile_mismatch"


def test_comment_listing_follows_pagination(monkeypatch):
    from hermes_notion import notion_client
    paths = []
    def request(token, path, **kw):
        paths.append(path)
        if len(paths) == 1:
            return {"results": [{"id": "first"}], "has_more": True, "next_cursor": "next cursor"}
        return {"results": [{"id": "last"}], "has_more": False}
    monkeypatch.setattr(notion_client, "_request", request)
    assert notion_client.get_comments_for_block("fake", "block") == [{"id": "first"}, {"id": "last"}]
    assert "start_cursor=next+cursor" in paths[1]


def test_signature_does_not_authorize_foreign_integration():
    import hashlib, hmac
    obj = instance()
    obj.settings.webhook_secret = "fake-signing-secret"
    obj.settings.bot_integration_id = "our-integration"
    req = Request({"integration_id": "foreign", "type": "comment.created", "entity": {"type": "comment", "id": "c1"}})
    req.headers = {"X-Notion-Signature": "sha256=" + hmac.new(b"fake-signing-secret", req.body, hashlib.sha256).hexdigest()}
    obj._spawn = lambda coro: coro.close()
    assert asyncio.run(obj._handle_webhook(req)).status == 403


@pytest.mark.parametrize("text, reason", [
    ("@greta FYI: the meeting moved", "non_actionable_update"),
    ("Greta, status: still working", "non_actionable_update"),
    ("FYI: no action needed", "non_actionable_update"),
    ("@greta " + "x" * 8200, "request_budget_exceeded"),
])
def test_non_requests_do_not_start_turns(text, reason):
    settings = NotionSettings(profile="greta", allowed_user_ids=["human"])
    routed = router.evaluate_comment(human_comment(text), settings, "greta")
    assert not routed.actionable
    assert routed.reason == reason


def test_ack_with_instruction_is_not_silently_discarded():
    assert not router.is_terminal_acknowledgment("thanks delete it", ["greta"])


def test_own_bot_user_id_is_suppressed_even_if_allowlisted():
    settings = NotionSettings(profile="greta", bot_user_id="human", allowed_user_ids=["human"])
    assert router.evaluate_comment(human_comment("@greta help"), settings).reason == "authored_by_target_bot"


def test_ingress_pending_budget():
    import hmac, hashlib
    obj = instance()
    obj.settings.webhook_secret = "fake-secret"
    obj._background = {object() for _ in range(32)}
    req = Request({"type": "comment.created", "entity": {"id": "c1", "type": "comment"}})
    req.headers = {"X-Notion-Signature": "sha256=" + hmac.new(b"fake-secret", req.body, hashlib.sha256).hexdigest()}
    obj._spawn = lambda c: pytest.fail("pending budget must prevent spawning")
    assert asyncio.run(obj._handle_webhook(req)).status == 429


def test_agent_dispatch_has_wall_clock_budget(monkeypatch):
    from hermes_notion import notion_client
    obj = instance()
    obj.settings.token = "fake-token"
    obj.settings.allowed_user_ids = ["human"]
    obj.settings.allowed_root_ids = ["root"]
    monkeypatch.setattr(notion_client, "get_comment", lambda *a: human_comment("@greta explain"))
    monkeypatch.setattr(adapter, "MAX_TURN_SECONDS", 0.001, raising=False)
    async def handle(event):
        await asyncio.sleep(10)
        pytest.fail("turn must be cancelled at budget")
    obj.handle_message = handle
    asyncio.run(obj._process_comment_id("c1", "greta"))
    assert storage.is_comment_processed("c1")


def test_replay_claim_is_atomic_and_retained():
    assert storage.claim_comment("once")
    assert not storage.claim_comment("once")
    for i in range(1005):
        storage.mark_comment_processed(str(i))
    assert storage.is_comment_processed("once")


def test_profile_label_cannot_select_foreign_runtime():
    with pytest.raises(ValueError, match="profile runtime mismatch"):
        NotionSettings.from_config({"profile": "greta"})


def test_api_errors_do_not_echo_response_content(monkeypatch, caplog):
    import io, urllib.error
    from hermes_notion import notion_client
    def fail(*a, **kw):
        raise urllib.error.HTTPError("https://api.notion.com", 403, "forbidden", {},
                                     io.BytesIO(b'{"message":"private-document-marker","code":"restricted_resource"}'))
    monkeypatch.setattr(notion_client.urllib.request, "urlopen", fail)
    with pytest.raises(notion_client.NotionClientError) as exc:
        notion_client.get_comment("fake-token", "c1")
    assert "private-document-marker" not in str(exc.value)
    assert "private-document-marker" not in caplog.text


def test_generic_health_uses_owning_profile():
    obj = instance()
    obj.settings.profile = "aroa"
    request = Request({})
    request.path = "/webhooks/notion"
    response = asyncio.run(obj._handle_health(request))
    assert "[aroa]" in response.text
