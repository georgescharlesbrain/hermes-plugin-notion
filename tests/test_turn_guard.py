from types import SimpleNamespace
import pytest
from hermes_notion import adapter, guard, storage
from gateway.config import Platform


@pytest.mark.parametrize("name", ["terminal", "execute_code", "write_file", "browser_navigate",
                                 "delegate_task", "mcp_notion_update_page", "notion_reply_comment",
                                 "asana_comment", "unknown_plugin_tool"])
def test_automated_turn_blocks_all_other_tool_paths(monkeypatch, name):
    monkeypatch.setattr(guard, "get_session_env", lambda key, default="":
                        {"HERMES_SESSION_PLATFORM": "notion"}.get(key, default))
    assert guard.check(name, {})["action"] == "block"


def test_guard_does_not_change_other_platforms(monkeypatch):
    monkeypatch.setattr(guard, "get_session_env", lambda key, default="": "asana")
    assert guard.check("terminal", {}) is None


def test_guard_checks_current_discussion_owner(monkeypatch):
    env = {"HERMES_SESSION_PLATFORM": "notion", "HERMES_SESSION_THREAD_ID": "discussion",
           "HERMES_SESSION_PROFILE": "greta"}
    monkeypatch.setattr(guard, "get_session_env", lambda key, default="": env.get(key, default))
    storage.set_discussion_owner("discussion", "greta")
    assert guard.check("notion_get_comments", {}) is None
    storage.set_discussion_owner("discussion", "stopped")
    assert guard.check("notion_get_comments", {})["action"] == "block"


def test_adapter_suppresses_default_mcp_tools():
    obj = object.__new__(adapter.NotionAdapter)
    obj.platform = "notion"
    source = SimpleNamespace(platform=obj.platform, profile="greta")
    assert obj.toolsets_for_source(source) == ["notion", "no_mcp"]
    assert obj.toolsets_for_source(SimpleNamespace(platform="asana")) is None


def test_no_mcp_sentinel_is_honored_by_the_installed_core(monkeypatch):
    from hermes_cli import tools_config
    monkeypatch.setattr(tools_config, "_get_plugin_toolset_keys", lambda: {"notion"})
    config = {"platform_toolsets": {"notion": ["notion", "no_mcp"]},
              "known_plugin_toolsets": {"notion": ["notion"]},
              "mcp_servers": {"notion": {"enabled": True}, "external": {"enabled": True}}}
    assert "external" not in tools_config._get_platform_tools(config, "notion")
    assert "no_mcp" not in tools_config._get_platform_tools(config, "notion")


def test_real_gateway_session_context_reaches_guard():
    from gateway.session_context import set_session_vars, clear_session_vars
    storage.set_discussion_owner("discussion", "greta")
    tokens = set_session_vars(platform="notion", thread_id="discussion", profile="greta")
    try:
        assert guard.check("notion_get_comments", {}) is None
        assert guard.check("terminal", {})["action"] == "block"
    finally:
        clear_session_vars(tokens)
