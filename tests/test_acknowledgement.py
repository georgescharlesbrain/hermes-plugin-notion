import asyncio
from unittest.mock import Mock
import pytest
from hermes_notion import adapter, notion_client, storage
from test_page_sessions import obj, comment
REAL_UPDATE = notion_client.update_comment

def setup(monkeypatch):
    instance = obj()
    comments = {"c1": comment("c1", "d1", "greta ping"),
                "c2": comment("c2", "d2", "greta ping")}
    monkeypatch.setattr(notion_client, "get_comment", lambda t, cid: comments[cid] if cid in comments else {"id": cid, "discussion_id": "d1"})
    ack = Mock(side_effect=lambda **kw: {"id": "ack-" + kw["discussion_id"]})
    patch = Mock(side_effect=lambda **kw: {"id": kw["comment_id"]})
    monkeypatch.setattr(notion_client, "create_acknowledgement", ack)
    monkeypatch.setattr(notion_client, "update_comment", patch)
    return instance, ack, patch

def test_ack_precedes_model_and_final_updates_same_comment(monkeypatch):
    instance, ack, patch = setup(monkeypatch)
    post = Mock()
    monkeypatch.setattr(notion_client, "create_comment_reply", post)
    async def handle(event):
        assert ack.call_count == 1
        assert storage.get_acknowledgement("c1") == "ack-d1"
        result = await instance.send(event.source.chat_id, "Pong", reply_to="c1")
        assert result.success, result.error
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "greta"))
    assert ack.call_args.kwargs["content"] == "I received your comment. I am preparing a reply."
    assert patch.call_args.kwargs["comment_id"] == "ack-d1"
    assert patch.call_args.kwargs["content"] == "Pong"
    post.assert_not_called()

def test_duplicate_and_foreign_address_do_not_ack(monkeypatch):
    instance, ack, patch = setup(monkeypatch)
    async def handle(event): pass
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "greta"))
    asyncio.run(instance._process_comment_id("c1", "greta"))
    assert ack.call_count == 1
    monkeypatch.setattr(notion_client, "get_comment", lambda t,c: comment(c, "d1", "aroa ping"))
    asyncio.run(instance._process_comment_id("foreign", "greta"))
    assert ack.call_count == 1

def test_second_ack_does_not_wait_for_first_model(monkeypatch):
    instance, ack, patch = setup(monkeypatch)
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def handle(event):
            if event.message_id == "c1":
                entered.set()
                await release.wait()
        instance.handle_message = handle
        first = asyncio.create_task(instance._process_comment_id("c1", "greta"))
        await entered.wait()
        second = asyncio.create_task(instance._process_comment_id("c2", "greta"))
        for _ in range(100):
            if ack.call_count == 2: break
            await asyncio.sleep(.01)
        assert ack.call_count == 2
        release.set()
        await asyncio.gather(first, second)
    asyncio.run(run())

def test_failed_update_does_not_create_duplicate(monkeypatch):
    instance, ack, patch = setup(monkeypatch)
    patch.side_effect = RuntimeError("network failure")
    post = Mock()
    monkeypatch.setattr(notion_client, "create_comment_reply", post)
    async def handle(event):
        result = await instance.send(event.source.chat_id, "Pong", reply_to="c1")
        assert not result.success
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "greta"))
    post.assert_not_called()

def test_ack_storage_is_profile_local(tmp_path):
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    marker = set_hermes_home_override(str(tmp_path / "first"))
    try: storage.save_acknowledgement("c1", "a1")
    finally: reset_hermes_home_override(marker)
    marker = set_hermes_home_override(str(tmp_path / "second"))
    try: assert storage.get_acknowledgement("c1") is None
    finally: reset_hermes_home_override(marker)

def test_update_uses_new_version_without_changing_other_requests(monkeypatch):
    calls = []
    monkeypatch.setattr(notion_client, "update_comment", REAL_UPDATE)
    monkeypatch.setattr(notion_client, "_request", lambda *a, **kw: calls.append((a,kw)) or {"id": "ack"})
    notion_client.update_comment("fixture", "ack", "Pong")
    args, kw = calls[0]
    assert args[1] == "/comments/ack"
    assert kw["method"] == "PATCH"
    assert kw["version"] == "2026-03-11"
    assert kw["data"]["rich_text"][0]["text"]["content"] == "Pong"

def test_receipt_burst_counts_new_comments_but_patch_does_not(monkeypatch):
    instance, ack, patch = setup(monkeypatch)
    monkeypatch.setattr(notion_client, "get_comment", lambda t,c: comment(c, "d1", "greta ping") if not c.startswith("ack-") else {"id": c, "discussion_id": "d1"})
    async def handle(event): pass
    instance.handle_message = handle
    async def run():
        for i in range(7):
            await instance._process_comment_id("burst" + str(i), "greta")
        assert ack.call_count == 5
        # A receipt already owns its slot; even a tripped new-comment breaker cannot block PATCH.
        result = await instance.send("notion:page:root", "Done", reply_to="burst0")
        assert result.success, result.error
    asyncio.run(run())
    assert patch.call_count == 1

@pytest.mark.parametrize("fault", ["post", "save"])
def test_ambiguous_receipt_does_not_dispatch_or_post_again(monkeypatch, fault):
    instance, ack, patch = setup(monkeypatch)
    if fault == "post":
        ack.side_effect = RuntimeError("ambiguous")
    else:
        save = storage.save_acknowledgement
        def failing_save(cid, rid):
            if rid: raise RuntimeError("disk failure")
            save(cid, rid)
        monkeypatch.setattr(storage, "save_acknowledgement", failing_save)
    async def forbidden(event): pytest.fail("Unverified receipt must not dispatch")
    instance.handle_message = forbidden
    post = Mock()
    monkeypatch.setattr(notion_client, "create_comment_reply", post)
    asyncio.run(instance._process_comment_id("c1", "greta"))
    assert ack.call_count == 1
    assert storage.acknowledgement_state("c1") == {"reply_id": None, "finished": 0, "final_attempt": 0}
    result = asyncio.run(instance.send("notion:page:root", "Done", reply_to="c1"))
    assert result.error == "acknowledgement_unverified"
    post.assert_not_called()

def test_error_after_final_does_not_overwrite_answer(monkeypatch):
    instance, ack, patch = setup(monkeypatch)
    async def handle(event):
        assert (await instance.send(event.source.chat_id, "Done", reply_to="c1")).success
        raise RuntimeError("after delivery")
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "greta"))
    assert patch.call_count == 1
    assert patch.call_args.kwargs["content"] == "Done"

def test_receipt_foreign_author_denies_update(monkeypatch):
    instance, ack, patch = setup(monkeypatch)
    instance.settings.bot_user_id = "own-bot"
    async def handle(event):
        result = await instance.send(event.source.chat_id, "Done", reply_to="c1")
        assert not result.success
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "greta"))
    patch.assert_not_called()


def test_ambiguous_final_readback_cannot_trigger_error_overwrite(monkeypatch):
    instance, ack, patch = setup(monkeypatch)
    get = notion_client.get_comment
    def failing_readback(token, cid):
        if cid == "ack-d1" and patch.call_count:
            raise RuntimeError("readback failed after write")
        return get(token, cid)
    monkeypatch.setattr(notion_client, "get_comment", failing_readback)
    async def handle(event):
        result = await instance.send(event.source.chat_id, "Done", reply_to="c1")
        assert not result.success
        raise RuntimeError("delivery reported failed")
    instance.handle_message = handle
    asyncio.run(instance._process_comment_id("c1", "greta"))
    assert patch.call_count == 1
    assert patch.call_args.kwargs["content"] == "Done"
    assert storage.acknowledgement_state("c1")["final_attempt"] == 1
