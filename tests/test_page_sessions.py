import asyncio
from types import SimpleNamespace
import pytest
from hermes_constants import get_hermes_home, set_hermes_home_override, reset_hermes_home_override
from hermes_notion import adapter, storage, notion_client, router
from hermes_notion.settings import NotionSettings
from gateway.config import PlatformConfig


def comment(cid, discussion, text, page="root"):
    return {"id": cid, "discussion_id": discussion, "parent": {"page_id": page},
            "created_by": {"id": "human", "type": "person"},
            "created_time": "2026-10-14T10:00:00Z",
            "rich_text": [{"plain_text": text, "type": "text"}]}


def obj(profile="greta"):
    result = object.__new__(adapter.NotionAdapter)
    result.settings = NotionSettings(profile=profile, token="fixture",
                                    allowed_root_ids=["root"], allowed_user_ids=["human"])
    result._home = get_hermes_home()
    result._processing = asyncio.Lock()
    result.build_source = lambda **kw: SimpleNamespace(profile=profile, **kw)
    return result


def test_two_discussions_use_one_page_source_and_distinct_reply_anchors(monkeypatch):
    instance = obj()
    comments = {"c1": comment("c1", "d1", "greta ping"),
                "c2": comment("c2", "d2", "greta ping")}
    monkeypatch.setattr(notion_client, "get_comment", lambda t, cid: comments[cid])
    events = []
    async def handle(event):
        events.append(event)
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "greta"))
    asyncio.run(instance._process_comment_id("c2", "greta"))
    assert len(events) == 2
    assert {e.source.chat_id for e in events} == {"notion:page:root"}
    assert all(e.source.thread_id is None and e.source.chat_type == "dm" for e in events)
    assert [e.message_id for e in events] == ["c1", "c2"]
    assert [e.metadata["discussion_id"] for e in events] == ["d1", "d2"]
    assert storage.get_discussion_page("d1") == storage.get_discussion_page("d2") == "root"
    assert all("Exact highlighted text is not available" in e.text for e in events)


@pytest.mark.parametrize("named_home", [False, True])
def test_comment_prompt_loads_conceptual_guidance_only_in_default_home(monkeypatch, tmp_path, named_home):
    instance = obj(profile="aroa")
    if named_home:
        instance._home = tmp_path / "profiles" / "aroa"
    monkeypatch.setattr(notion_client, "get_comment", lambda *a: comment("c1", "d1", "aroa ping"))
    events = []
    async def handle(event):
        events.append(event)
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "aroa"))
    assert len(events) == 1
    assert "skill_view(name='notion:use')" in events[0].text
    assert ("skill_view(name='knowledge-management')" in events[0].text) is (not named_home)
    if not named_home:
        assert "technical" in events[0].text
        assert "conceptual" in events[0].text


def test_foreign_address_then_followup_does_not_dispatch_in_previous_owner(monkeypatch):
    instance = obj()
    storage.set_discussion_owner("d1", "greta")
    comments = {"c1": comment("c1", "d1", "aroa ping"),
                "c2": comment("c2", "d1", "tell me more")}
    monkeypatch.setattr(notion_client, "get_comment", lambda t, cid: comments[cid])
    async def forbidden(event):
        pytest.fail("Greta must not reply")
    instance.handle_message = forbidden
    asyncio.run(instance._process_comment_id("c1", "greta"))
    assert storage.get_discussion_owner("d1") == "aroa"
    asyncio.run(instance._process_comment_id("c2", "greta"))


def test_followup_reuses_its_discussion_owner_not_another_discussion(monkeypatch):
    instance = obj()
    storage.set_discussion_owner("d1", "greta")
    storage.set_discussion_owner("d2", "aroa")
    comments = {"c1": comment("c1", "d1", "tell me more"), "c2": comment("c2", "d2", "tell me more")}
    monkeypatch.setattr(notion_client, "get_comment", lambda t, cid: comments[cid])
    events = []
    async def handle(event):
        events.append(event)
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "greta"))
    asyncio.run(instance._process_comment_id("c2", "greta"))
    assert [e.message_id for e in events] == ["c1"]


def test_profile_states_remain_private(tmp_path):
    for profile, owner in (("default", "aroa"), ("greta", "greta")):
        home = tmp_path / profile
        marker = set_hermes_home_override(str(home))
        try:
            assert storage.get_discussion_owner("d1") is None
            storage.assign_discussion_owner("d1", owner, "2026-10-14T10:00:00Z", "c1")
            storage.set_discussion_page("d1", "root")
            assert storage.get_discussion_owner("d1") == owner
            assert storage.data_dir() == home / "plugin-data" / "notion"
        finally:
            reset_hermes_home_override(marker)
    assert not (tmp_path / "shared-plugin-data").exists()


def test_old_handoff_cannot_replace_new_owner():
    assert storage.assign_discussion_owner("d1", "aroa", "2026-10-14T10:02:00Z", "c2")
    assert not storage.assign_discussion_owner("d1", "greta", "2026-10-14T10:01:00Z", "c1")
    assert storage.get_discussion_owner("d1") == "aroa"


def test_reply_recovers_discussion_from_anchor_without_event_metadata(monkeypatch):
    instance = obj()
    for cid, disc in (("c1", "d1"), ("c2", "d2")):
        storage.set_discussion_owner(disc, "greta")
        storage.set_discussion_parent(disc, "root")
        storage.set_discussion_page(disc, "root")
    comments = {"c1": comment("c1", "d1", "greta ping"), "c2": comment("c2", "d2", "greta ping")}
    writes = []
    def get(token, cid):
        return comments[cid] if cid in comments else {"id": cid, "discussion_id": cid.removeprefix("reply-")}
    monkeypatch.setattr(notion_client, "get_comment", get)
    def post(**kw):
        writes.append(kw)
        return {"id": "reply-" + kw["discussion_id"]}
    monkeypatch.setattr(notion_client, "create_comment_reply", post)
    for cid in ("c1", "c2"):
        result = asyncio.run(instance.send("notion:page:root", "pong", reply_to=cid))
        assert result.success, result.error
    assert [w["discussion_id"] for w in writes] == ["d1", "d2"]


def test_page_reply_denies_wrong_or_missing_anchor(monkeypatch):
    instance = obj()
    monkeypatch.setattr(notion_client, "get_comment", lambda *a: comment("c1", "d1", "greta ping", "another"))
    assert asyncio.run(instance.send("notion:page:root", "pong")).error == "missing_reply_anchor"
    assert asyncio.run(instance.send("notion:page:root", "pong", reply_to="c1")).error == "request_page_mismatch"


@pytest.mark.parametrize("profile,names", [("aroa", ["aroa", "arroa"]), ("greta", ["greta"])])
def test_plain_foreign_prefix_never_continues_owned_discussion(profile, names):
    other = "greta" if profile == "aroa" else "aroa"
    settings = NotionSettings(profile=profile, mention_names=names, allowed_user_ids=["human"])
    assert router.evaluate_comment(comment("c1", "d1", other + " ping"), settings, profile).reason == "addressed_to_other_user"


def test_runtime_profile_uses_actual_home_not_logical_bot(monkeypatch, tmp_path):
    monkeypatch.setattr(NotionSettings, "from_config", classmethod(lambda cls, *a: NotionSettings(profile="aroa", token="fixture")))
    from gateway.config import Platform
    monkeypatch.setattr(adapter, "Platform", lambda _: Platform.TELEGRAM)
    instance = adapter.NotionAdapter(PlatformConfig())
    source = instance.build_source(chat_id="notion:page:root", chat_type="channel", thread_id=None)
    assert source.profile == "default"
    assert source.profile != "aroa"

def test_page_guard_uses_current_comment_even_if_another_discussion_is_owned(monkeypatch):
    from hermes_notion import guard
    from gateway.session_context import set_session_vars, clear_session_vars
    storage.set_discussion_page("current", "root")
    storage.set_discussion_page("other", "root")
    storage.set_discussion_owner("current", "greta")
    storage.set_discussion_owner("other", "greta")
    storage.bind_comment_discussion("comment", "current")
    tokens = set_session_vars(platform="notion", chat_id="notion:page:root",
                              message_id="comment", profile="greta")
    try:
        assert guard.check("notion_get_comments", {}) is None
        storage.set_discussion_owner("current", "stopped")
        assert guard.check("notion_get_comments", {})["action"] == "block"
        storage.set_discussion_owner("current", "aroa")
        assert guard.check("notion_get_comments", {})["action"] == "block"
    finally:
        clear_session_vars(tokens)


def test_unknown_page_comment_guard_fails_closed():
    from hermes_notion import guard
    from gateway.session_context import set_session_vars, clear_session_vars
    tokens = set_session_vars(platform="notion", chat_id="notion:page:root",
                              message_id="unknown", profile="greta")
    try:
        assert guard.check("notion_get_comments", {})["action"] == "block"
    finally:
        clear_session_vars(tokens)


def test_containing_page_resolution_is_bounded(monkeypatch):
    objects = {"leaf": {"parent": {"block_id": "container"}},
               "container": {"parent": {"page_id": "root"}},
               "cycle": {"parent": {"block_id": "cycle"}}}
    monkeypatch.setattr(notion_client, "get_block", lambda t, i: objects[i])
    assert adapter._comment_page("fixture", {"parent": {"block_id": "leaf"}}) == "root"
    assert adapter._comment_page("fixture", {"parent": {"block_id": "cycle"}}) is None


def test_actual_hermes_session_key_is_same_for_different_page_discussions():
    from gateway.session import build_session_key, SessionSource
    from gateway.config import Platform
    # The key builder's namespace logic is platform-independent.
    first = SessionSource(platform=Platform.TELEGRAM, chat_id="notion:page:root", chat_type="dm",
                          profile="greta", thread_id=None, user_id="human")
    second = SessionSource(platform=Platform.TELEGRAM, chat_id="notion:page:root", chat_type="dm",
                           profile="greta", thread_id=None, user_id="another-human")
    assert build_session_key(first, profile=first.profile) == build_session_key(second, profile=second.profile)
    second.profile = "default"
    assert build_session_key(first, profile=first.profile) != build_session_key(second, profile=second.profile)
