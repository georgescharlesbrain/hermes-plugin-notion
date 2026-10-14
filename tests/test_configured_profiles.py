"""Configured arbitrary profiles retain isolated authority, routing, tools and state."""
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent.secret_scope import set_secret_scope, reset_secret_scope, set_multiplex_context, reset_multiplex_context
from gateway.session_context import set_session_vars, clear_session_vars
from hermes_constants import set_hermes_home_override, reset_hermes_home_override
from hermes_notion import adapter, guard, ntn, policy, router, storage, notion_client
from hermes_notion.settings import NotionSettings

ROOT = "11111111-1111-4111-8111-111111111111"
OUTSIDE = "22222222-2222-4222-8222-222222222222"

def config(name="luna"):
    return {"profile": name, "bot_user_id": "bot-" + name, "bot_integration_id": "integration-" + name,
            "mention_names": [name], "allowed_user_ids": ["human-" + name], "allowed_root_ids": [ROOT],
            "port": 8650, "peer_agents": [{"profile": "greta", "mention_names": ["greta"], "bot_user_id": "bot-greta"}]}

def settings(monkeypatch, tmp_path, name="luna"):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / name))
    monkeypatch.setattr("hermes_notion.settings._scoped_secret", lambda key: "fake-" + name if key == "NOTION_API_TOKEN" else "")
    return NotionSettings.from_config(config(name))

def comment(name="luna", text=None, cid="c", discussion="d"):
    return {"id": cid, "discussion_id": discussion, "parent": {"page_id": ROOT},
            "created_by": {"id": "human-" + name, "type": "person"},
            "rich_text": [{"type": "text", "plain_text": text or name + ", explain this"}]}

def test_new_profile_has_only_configured_identity_and_permissions(monkeypatch, tmp_path):
    result = settings(monkeypatch, tmp_path)
    assert result.profile == "luna"
    assert result.bot_user_id == "bot-luna"
    assert result.allowed_user_ids == ["human-luna"]
    assert result.allowed_root_ids == [ROOT]
    assert result.token == "fake-luna"
    assert not result.allow_workspace_access

@pytest.mark.parametrize("field", ["bot_user_id", "bot_integration_id", "mention_names", "allowed_user_ids", "allowed_root_ids"])
def test_new_profile_requires_explicit_configuration(monkeypatch, tmp_path, field):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "luna"))
    extra = config()
    extra.pop(field)
    with pytest.raises(ValueError):
        NotionSettings.from_config(extra)

def test_profile_cannot_impersonate_another_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "luna"))
    with pytest.raises(ValueError):
        NotionSettings.from_config(config("greta"))

def test_generic_policy_is_root_scoped_and_explicit_workspace_is_required():
    assert policy.check_mutation_gate("luna", "fake", ROOT, "update", [ROOT], ["human-luna"], "human-luna").allowed
    assert not policy.check_mutation_gate("luna", "fake", ROOT, "update", [], ["human-luna"], "human-luna").allowed
    assert not policy.check_mutation_gate("luna", "fake", ROOT, "update", ["*"], ["human-luna"], "human-luna").allowed
    assert policy.check_mutation_gate("luna", "fake", ROOT, "update", ["*"], ["human-luna"], "human-luna", allow_workspace_access=True).allowed
    assert not policy.check_mutation_gate("luna", "fake", ROOT, "update", [ROOT], ["human-luna"], "other").allowed

def test_peer_aliases_override_owned_thread_and_do_not_grant_human_authority(monkeypatch, tmp_path):
    result = settings(monkeypatch, tmp_path)
    result.peer_agents = [{"profile": "atlas", "mention_names": ["atlas"], "bot_user_id": "bot-atlas"}]
    assert router.evaluate_comment(comment(text="Atlas, explain this"), result, "luna").reason == "addressed_to_other_user"
    assert router.evaluate_comment(comment(), result).actionable
    assert not router.evaluate_comment(comment("atlas"), result).actionable

def test_arbitrary_profile_guard_and_delete_approval(monkeypatch, tmp_path):
    result = settings(monkeypatch, tmp_path)
    storage.set_discussion_page("d", ROOT)
    storage.set_discussion_parent("d", ROOT)
    storage.set_discussion_owner("d", "luna")
    storage.bind_comment_discussion("c", "d")
    marker = set_session_vars(platform="notion", chat_id="notion:page:" + ROOT, message_id="c", profile="luna")
    try:
        assert guard.check("notion_ntn", {}) is None
        assert ntn._approved_delete(comment(text="Luna, approve-delete " + ROOT), [ROOT], result.mention_names)
        assert not ntn._approved_delete(comment(text="Greta, approve-delete " + ROOT), [ROOT], result.mention_names)
        storage.set_discussion_owner("d", "greta")
        assert guard.check("notion_ntn", {})["action"] == "block"
    finally:
        clear_session_vars(marker)

def test_three_profiles_do_not_share_credentials_or_replay_state(tmp_path):
    multi = set_multiplex_context(True)
    try:
        for name in ("luna", "atlas", "nova", "luna"):
            home = tmp_path / "profiles" / name
            home.mkdir(parents=True, exist_ok=True)
            marker = set_hermes_home_override(str(home))
            scope = set_secret_scope({"NOTION_API_TOKEN": "fake-" + name})
            try:
                result = NotionSettings.from_config(config(name))
                assert result.token == "fake-" + name
                assert storage.data_dir() == home / "plugin-data" / "notion"
                assert storage.get_discussion_owner("shared-id") in (None, name)
                storage.set_discussion_owner("shared-id", name)
                assert storage.get_discussion_owner("shared-id") == name
            finally:
                reset_secret_scope(scope)
                reset_hermes_home_override(marker)
    finally:
        reset_multiplex_context(multi)

def test_third_profile_dispatch_reuses_page_session_and_keeps_thread_anchor(monkeypatch, tmp_path):
    result = settings(monkeypatch, tmp_path)
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = result
    from hermes_constants import get_hermes_home
    obj._home = get_hermes_home()
    obj._processing = asyncio.Lock()
    obj._turn_processing = asyncio.Lock()
    obj.build_source = lambda **kw: SimpleNamespace(profile="luna", **kw)
    events = []
    async def handle(event):
        events.append(event)
    obj.handle_message = handle
    monkeypatch.setattr(notion_client, "get_comment", lambda token, cid: comment(cid=cid, discussion="d-" + cid))
    async def run():
        await obj._process_comment_id("c1", "luna")
        await obj._process_comment_id("c2", "luna")
    asyncio.run(run())
    assert [event.source.chat_id for event in events] == ["notion:page:" + ROOT] * 2
    assert [event.metadata["discussion_id"] for event in events] == ["d-c1", "d-c2"]

def test_third_profile_ntn_uses_guarded_private_environment(monkeypatch, tmp_path):
    result = settings(monkeypatch, tmp_path)
    monkeypatch.setattr(ntn.shutil, "which", lambda _: "/installed/ntn")
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="{}", stderr=""))
    monkeypatch.setattr(ntn.subprocess, "run", run)
    assert ntn.execute({"args": ["api", "v1/blocks/" + ROOT, "-X", "PATCH"], "body": {"paragraph": {}}}, result)["ok"]
    assert run.call_args.kwargs["env"]["NOTION_API_TOKEN"] == "fake-luna"
    assert "/profiles/luna/plugin-data/notion/cli" in run.call_args.kwargs["cwd"]


def test_third_profile_signed_ingress_is_bound_to_its_own_route(monkeypatch, tmp_path):
    import hashlib
    import hmac
    import json
    result = settings(monkeypatch, tmp_path)
    result.webhook_secret = "fake-private-signing-secret"
    obj = object.__new__(adapter.NotionAdapter)
    obj.settings = result
    from hermes_constants import get_hermes_home
    obj._home = get_hermes_home()
    obj._background = set()
    seen = []
    def spawn(coro):
        seen.append(True)
        coro.close()
    obj._spawn = spawn
    payload = {"type": "comment.created", "integration_id": result.bot_integration_id,
               "entity": {"type": "comment", "id": "third-profile-comment"}}
    class Request:
        path = "/webhooks/notion/luna"
        body = json.dumps(payload).encode()
        content_length = len(body)
        headers = {"X-Notion-Signature": "sha256=" + hmac.new(
            result.webhook_secret.encode(), body, hashlib.sha256).hexdigest()}
        async def read(self):
            return self.body
    request = Request()
    assert asyncio.run(obj._handle_webhook(request)).status == 200
    assert seen == [True]
    request.path = "/webhooks/notion/greta"
    assert asyncio.run(obj._handle_webhook(request)).status == 404
    request.path = "/webhooks/notion/luna"
    request.headers = {"X-Notion-Signature": "sha256=invalid"}
    assert asyncio.run(obj._handle_webhook(request)).status == 401
    assert seen == [True]


def test_real_registry_dispatch_for_a_configured_third_profile(monkeypatch, tmp_path):
    import json
    from hermes_notion import tools
    from tools.registry import ToolRegistry
    result = settings(monkeypatch, tmp_path)
    monkeypatch.setattr(tools, "_settings", lambda: result)
    monkeypatch.setattr(ntn.shutil, "which", lambda _: "/installed/ntn")
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout='{"verified":true}', stderr=""))
    monkeypatch.setattr(ntn.subprocess, "run", run)
    registry = ToolRegistry()
    registry.register(name="notion_ntn", toolset="notion", schema=tools.SCHEMAS["notion_ntn"],
                      handler=tools.HANDLERS["notion_ntn"], check_fn=lambda: True)
    answer = json.loads(registry.dispatch("notion_ntn", {"args": ["api", "v1/blocks/" + ROOT]}))
    assert answer["ok"]
    assert run.call_args.kwargs["env"]["NOTION_API_TOKEN"] == "fake-luna"

@pytest.mark.parametrize("name", ["luna", "aroa"])
def test_named_profile_cannot_inherit_legacy_grants(monkeypatch, tmp_path, name):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / name))
    extra = config(name)
    extra.pop("allowed_user_ids")
    with pytest.raises(ValueError):
        NotionSettings.from_config(extra)


def test_configured_profile_requirements_load_the_actual_profile_config(monkeypatch, tmp_path):
    import hermes_yaml as yaml
    from hermes_notion import tools
    result = settings(monkeypatch, tmp_path)
    from hermes_constants import get_hermes_home
    home = get_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(yaml.safe_dump({"platforms": {"notion": {"extra": config()}}}))
    assert adapter.check_requirements()
    assert tools.check_requirements()
    assert tools._settings().bot_user_id == result.bot_user_id


def test_three_profiles_keep_the_same_event_claim_private(tmp_path):
    for index, name in enumerate(("luna", "atlas", "nova", "luna")):
        marker = set_hermes_home_override(str(tmp_path / "profiles" / name))
        try:
            assert storage.claim_comment("same-vendor-comment") is (index < 3)
        finally:
            reset_hermes_home_override(marker)
