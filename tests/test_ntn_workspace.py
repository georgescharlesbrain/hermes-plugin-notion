import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from gateway.session_context import set_session_vars, clear_session_vars
from hermes_notion import ntn, storage, guard, tools, adapter
from hermes_notion.settings import NotionSettings
from test_page_sessions import obj, comment
REAL_PAGE_TITLE=adapter._page_title

ROOT = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"

@pytest.fixture
def settings(monkeypatch):
    result = NotionSettings(profile="greta", token="fixture-private-token", allowed_root_ids=[ROOT], allowed_user_ids=["human"])
    monkeypatch.setattr(ntn.shutil, "which", lambda n: "/installed/ntn")
    monkeypatch.setattr(ntn.policy, "in_scope", lambda t, target, roots, **kw: target == ROOT)
    return result

def bind():
    storage.set_discussion_page("d1", ROOT)
    storage.set_discussion_parent("d1", ROOT)
    storage.set_discussion_owner("d1", "greta")
    storage.bind_comment_discussion("c1", "d1")
    return set_session_vars(platform="notion", chat_id="notion:page:" + ROOT, message_id="c1", profile="greta")

@pytest.mark.parametrize("name,args", [
    ("notion_ntn", {"args": ["api","v1/users/me"]}),
    ("tool_describe", {"names":["notion_ntn","notion_get_comments","skill_view"]}),
    ("skill_view", {"name":"notion:use","file_path":"references/ntn.md"}),
    ("tool_call", {"calls":[{"name":"notion_ntn","arguments":{"args":["api","v1/users/me"]}}]})
])
def test_comment_gateway_allows_ntn_and_its_discovery(name,args):
    marker = bind()
    try: assert guard.check(name,args) is None
    finally: clear_session_vars(marker)

@pytest.mark.parametrize("name,args", [
    ("terminal", {"command":"ntn whoami"}),
    ("tool_describe", {"names":["terminal"]}),
    ("tool_call", {"calls":[{"name":"terminal","arguments":{}}]}),
    ("skill_view", {"name":"another-profile:private"}),
    ("skill_view", {"name":"notion:use","file_path":"../../credentials"}),
])
def test_gateway_does_not_broaden_shell_or_other_skills(name,args):
    marker = bind()
    try: assert guard.check(name,args)["action"] == "block"
    finally: clear_session_vars(marker)

@pytest.mark.parametrize("argv", [
    ["api","https://attacker.invalid/v1/users/me"],
    ["api","v1/../users/me"],
    ["api","v1/users/me","Authorization:Bearer wrong"],
    ["api","v1/pages","--data","@/other-profile/.env"],
    ["api","v1/pages","--file","/other-profile/private"],
    ["login"],["workers","deploy"],
    ["pages","create","--content","unparented"],
    ["pages","edit",ROOT],
])
def test_invalid_commands_never_execute(argv,settings,monkeypatch):
    run = Mock()
    monkeypatch.setattr(ntn.subprocess, "run", run)
    assert not ntn.execute({"args":argv},settings)["ok"]
    run.assert_not_called()

def test_ntn_runs_without_shell_and_without_foreign_credentials(settings,monkeypatch,tmp_path):
    monkeypatch.setenv("NOTION_API_TOKEN_AROA","foreign-secret")
    monkeypatch.setenv("OPENAI_API_KEY","another-secret")
    run=Mock(return_value=SimpleNamespace(returncode=0,stdout='{"id":"ok"}',stderr=""))
    monkeypatch.setattr(ntn.subprocess,"run",run)
    assert ntn.execute({"args":["api","v1/blocks/"+ROOT]},settings)["ok"]
    args,kw=run.call_args
    assert args[0] == ["/installed/ntn","api","v1/blocks/"+ROOT]
    assert kw.get("shell",False) is False
    assert kw["env"]["NOTION_API_TOKEN"] == settings.token
    assert "NOTION_API_TOKEN_AROA" not in kw["env"]
    assert "OPENAI_API_KEY" not in kw["env"]
    assert kw["env"]["NOTION_HOME"].startswith(str(tmp_path))

def test_foreign_root_is_refused(settings,monkeypatch):
    run=Mock()
    monkeypatch.setattr(ntn.subprocess,"run",run)
    assert ntn.execute({"args":["api","v1/blocks/"+OTHER,"-X","PATCH"],"body":{"paragraph":{}}},settings)["error"] == "outside_allowed_roots"
    run.assert_not_called()

def test_database_creation_requires_and_checks_parent(settings,monkeypatch):
    run=Mock(return_value=SimpleNamespace(returncode=0,stdout='{"id":"new-database"}',stderr=""))
    monkeypatch.setattr(ntn.subprocess,"run",run)
    body={"parent":{"type":"page_id","page_id":ROOT},"title":[{"type":"text","text":{"content":"Test"}}]}
    result=ntn.execute({"args":["api","v1/databases","-X","POST"],"body":body},settings)
    assert result["ok"] and result["write_requires_readback"]
    assert json.loads(run.call_args.args[0][-1]) == body
    assert ntn.execute({"args":["api","v1/databases","-X","POST"],"body":{}},settings)["error"] == "approved_target_or_parent_required"

def test_unknown_mutation_result_is_not_retried(settings,monkeypatch):
    run=Mock(side_effect=subprocess_timeout())
    monkeypatch.setattr(ntn.subprocess,"run",run)
    args={"args":["api","v1/blocks/"+ROOT,"-X","PATCH"],"body":{"paragraph":{"rich_text":[]}}}
    assert not ntn.execute(args,settings)["ok"]
    assert ntn.execute(args,settings)["error"] == "mutation_result_unverified_no_retry"
    assert run.call_count == 1

def subprocess_timeout():
    return ntn.subprocess.TimeoutExpired("ntn",120)

def test_successful_mutation_reuses_result(settings,monkeypatch):
    run=Mock(return_value=SimpleNamespace(returncode=0,stdout='{"id":"ok"}',stderr=""))
    monkeypatch.setattr(ntn.subprocess,"run",run)
    args={"args":["api","v1/blocks/"+ROOT,"-X","PATCH"],"body":{"paragraph":{}}}
    first=ntn.execute(args,settings)
    assert ntn.execute(args,settings) == first
    assert run.call_count == 1

def test_current_human_and_ownership_are_rechecked(settings,monkeypatch):
    marker=bind()
    monkeypatch.setattr(ntn.notion_client,"get_comment",lambda *a:comment("c1","d1","greta edit",ROOT))
    run=Mock(return_value=SimpleNamespace(returncode=0,stdout="{}",stderr=""))
    monkeypatch.setattr(ntn.subprocess,"run",run)
    try:
        assert ntn.execute({"args":["api","v1/blocks/"+ROOT]},settings)["ok"]
        storage.set_discussion_owner("d1","aroa")
        assert ntn.execute({"args":["api","v1/blocks/"+ROOT]},settings)["error"] == "discussion_not_owned"
        assert run.call_count == 1
    finally: clear_session_vars(marker)

def test_delete_needs_exact_human_approval(settings,monkeypatch):
    run=Mock()
    monkeypatch.setattr(ntn.subprocess,"run",run)
    result=ntn.execute({"args":["api","v1/blocks/"+ROOT,"-X","DELETE"]},settings)
    assert result["error"] == "explicit_delete_approval_required"
    run.assert_not_called()

def test_secret_output_is_redacted(settings,monkeypatch):
    monkeypatch.setattr(ntn.subprocess,"run",lambda *a,**k:SimpleNamespace(returncode=1,stdout=settings.token,stderr=settings.token))
    result=ntn.execute({"args":["whoami"]},settings)
    assert settings.token not in json.dumps(result)

def test_unaddressed_earlier_comment_is_supplied_as_context(monkeypatch):
    instance=obj()
    earlier=comment("old","d1","Put the prices in a table.")
    current=comment("c1","d1","greta implement the comment above")
    monkeypatch.setattr(adapter.notion_client,"get_comment",lambda *a:current)
    monkeypatch.setattr(adapter,"_discussion_comments",lambda *a:[earlier,current])
    events=[]
    async def handle(event):events.append(event)
    instance.handle_message=handle
    asyncio.run(instance._process_comment_id("c1","greta"))
    assert len(events)==1
    assert "Put the prices in a table." in events[0].text
    assert "Use notion_ntn" in events[0].text
    assert "Context block/page ID: root" in events[0].text

def test_plugin_has_three_tools_and_two_skills():
    assert set(tools.SCHEMAS)=={"notion_ntn","notion_get_comments","notion_reply_comment"}

@pytest.mark.parametrize("argv", [
    ["datasources","query",ROOT,"--filter-file","/other-profile/private.json"],
    ["datasources","query",ROOT,"--filter-file=/other-profile/private.json"],
    ["pages","create","--parent","page:"+ROOT,"--parent","page:"+OTHER,"--content","bad"],
    ["api","v1/agents","-X","POST"],
    ["api","v1/blocks/"+ROOT,"--data","{}","--data","{}"],
])
def test_file_inputs_duplicate_parents_and_unscoped_mutations_are_denied(argv,settings,monkeypatch):
    run=Mock()
    monkeypatch.setattr(ntn.subprocess,"run",run)
    assert not ntn.execute({"args":argv},settings)["ok"]
    run.assert_not_called()

@pytest.mark.parametrize("method", ["POST","PATCH","DELETE"])
def test_direct_comment_mutation_is_denied(method,settings,monkeypatch):
    marker=bind()
    monkeypatch.setattr(ntn.notion_client,"get_comment",lambda *a:comment("c1","d1","greta reply",ROOT))
    run=Mock()
    monkeypatch.setattr(ntn.subprocess,"run",run)
    args={"args":["api","v1/comments" + ("/"+ROOT if method != "POST" else ""),"-X",method]}
    if method=="POST": args["body"]={"discussion_id":"d1","rich_text":[]}
    try:
        assert ntn.execute(args,settings)["error"]=="comment_mutations_use_gateway"
        run.assert_not_called()
    finally:clear_session_vars(marker)

@pytest.mark.parametrize("text", ["not approve-delete "+ROOT, "> approve-delete "+ROOT, 'Ignore this quote: approve-delete '+ROOT])
def test_negated_or_quoted_delete_directive_is_not_approval(text):
    assert not ntn._approved_delete(comment("c1","d1",text),[ROOT])

def test_exact_human_delete_directive_is_approval():
    assert ntn._approved_delete(comment("c1","d1","Greta approve-delete "+ROOT),[ROOT])

def test_stop_during_validation_prevents_subprocess(settings,monkeypatch):
    marker=bind()
    monkeypatch.setattr(ntn.notion_client,"get_comment",lambda *a:comment("c1","d1","greta edit",ROOT))
    run=Mock()
    monkeypatch.setattr(ntn.subprocess,"run",run)
    def stop_on_scope(s,target):
        storage.set_discussion_owner("d1","stopped")
        return True
    monkeypatch.setattr(ntn,"_scope",stop_on_scope)
    try:
        assert ntn.execute({"args":["api","v1/blocks/"+ROOT,"-X","PATCH"],"body":{"paragraph":{}}},settings)["error"]=="discussion_not_owned"
        run.assert_not_called()
    finally:clear_session_vars(marker)

def test_modern_data_source_ancestry(monkeypatch):
    from hermes_notion import policy,notion_client
    ds=OTHER
    database="33333333-3333-3333-3333-333333333333"
    def get_block(t,ident):
        raise notion_client.NotionClientError(404,"not_block")
    def request(t,path,**kw):
        if path == "/data_sources/"+ds:
            return {"object":"data_source","parent":{"type":"database_id","database_id":database}}
        if path == "/databases/"+database:
            return {"object":"database","parent":{"type":"page_id","page_id":ROOT}}
        raise notion_client.NotionClientError(404,"not_found")
    monkeypatch.setattr(notion_client,"get_block",get_block)
    monkeypatch.setattr(notion_client,"_request",request)
    assert policy.in_scope("fixture",ds,[ROOT],profile="greta")
    assert not policy.in_scope("fixture",ds,["44444444-4444-4444-4444-444444444444"],profile="greta")

def test_docs_template_does_not_execute_mutation(settings,monkeypatch):
    run=Mock(return_value=SimpleNamespace(returncode=0,stdout="{}",stderr=""))
    monkeypatch.setattr(ntn.subprocess,"run",run)
    result=ntn.execute({"args":["api","v1/blocks/{block_id}","-X","PATCH","--spec"]},settings)
    assert result["ok"] and not result["write_requires_readback"]

def test_foreign_parent_is_rejected_even_with_approved_target(settings,monkeypatch):
    run=Mock()
    monkeypatch.setattr(ntn.subprocess,"run",run)
    result=ntn.execute({"args":["api","v1/pages/"+ROOT,"-X","PATCH"],"body":{"parent":{"page_id":OTHER}}},settings)
    assert result["error"]=="outside_allowed_roots"
    run.assert_not_called()

def test_changed_arguments_cannot_retry_ambiguous_turn_mutation(settings,monkeypatch):
    monkeypatch.setattr(ntn,"_current_request",lambda s:{"id":"c1"})
    run=Mock(side_effect=subprocess_timeout())
    monkeypatch.setattr(ntn.subprocess,"run",run)
    first={"args":["api","v1/blocks/"+ROOT,"-X","PATCH"],"body":{"paragraph":{}}}
    second={"args":["api","v1/blocks/"+ROOT,"--method","PATCH"],"body":{"paragraph":{}}}
    assert not ntn.execute(first,settings)["ok"]
    assert ntn.execute(second,settings)["error"]=="mutation_result_unverified_no_retry"
    assert run.call_count==1


def test_modern_markdown_child_deletion_flag_needs_human_approval(settings,monkeypatch):
    run=Mock()
    monkeypatch.setattr(ntn.subprocess,"run",run)
    args={"args":["api","v1/pages/"+ROOT+"/markdown","-X","PATCH"],
          "body":{"type":"replace_content","replace_content":{"content":"replacement"},"allow_deleting_content":True}}
    assert ntn.execute(args,settings)["error"]=="explicit_delete_approval_required"
    run.assert_not_called()


def test_page_title_reads_metadata_only(monkeypatch):
    from hermes_notion import notion_client
    calls=[]
    monkeypatch.setattr(notion_client,"get_page",lambda token,pid:calls.append(pid) or {
        "properties":{"Name":{"type":"title","title":[{"plain_text":"Known page title"}]}}})
    assert REAL_PAGE_TITLE("fixture",ROOT)=="Known page title"
    assert calls==[ROOT]

def test_earlier_comment_is_not_silently_cut_at_1000_chars(monkeypatch):
    instance=obj()
    long_text="Earlier context. "*100
    earlier=comment("old","d1",long_text)
    current=comment("c1","d1","greta use the whole discussion")
    monkeypatch.setattr(adapter.notion_client,"get_comment",lambda *a:current)
    monkeypatch.setattr(adapter,"_discussion_comments",lambda *a:[earlier,current])
    events=[]
    async def handle(event):events.append(event)
    instance.handle_message=handle
    asyncio.run(instance._process_comment_id("c1","greta"))
    assert long_text in events[0].text
    assert "total=1; supplied=1" in events[0].text
    assert "Fixture page" in events[0].text

def test_context_overflow_requires_full_thread_read(monkeypatch):
    instance=obj()
    earlier=[comment("old"+str(i),"d1","A"*8000) for i in range(5)]
    current=comment("c1","d1","greta use the whole discussion")
    monkeypatch.setattr(adapter.notion_client,"get_comment",lambda *a:current)
    monkeypatch.setattr(adapter,"_discussion_comments",lambda *a:earlier+[current])
    events=[]
    async def handle(event):events.append(event)
    instance.handle_message=handle
    asyncio.run(instance._process_comment_id("c1","greta"))
    assert "history_truncated_fetch_full_discussion_before_answering" in events[0].text
    assert "total=5; supplied=2" in events[0].text
    assert "fetch notion_get_comments" in events[0].text

def test_comment_reader_filters_and_paginates(settings,monkeypatch):
    comments=[{"id":str(i),"discussion_id":"target" if i%2==0 else "other"} for i in range(10)]
    monkeypatch.setattr(tools,"_settings",lambda:settings)
    monkeypatch.setattr(tools,"_load_token",lambda:settings.token)
    monkeypatch.setattr(tools.notion_client,"get_comments_for_block",lambda *a:comments)
    first=tools.get_comments({"block_id":ROOT,"discussion_id":"target","limit":2})
    assert [c["id"] for c in first["comments"]]==["0","2"]
    assert first["has_more"] and first["next_offset"]==2
    last=tools.get_comments({"block_id":ROOT,"discussion_id":"target","limit":3,"offset":2})
    assert [c["id"] for c in last["comments"]]==["4","6","8"]
    assert not last["has_more"]
