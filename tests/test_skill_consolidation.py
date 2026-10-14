from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from agent.skill_utils import parse_frontmatter

ROOT = Path(__file__).resolve().parents[1]


def wrapper():
    spec = spec_from_file_location("notion_cli_wrapper_test", ROOT / "skills/use/scripts/ntn_profile.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_two_skill_metadata_and_compatibility_path():
    for name in ("use", "profile-setup"):
        path = ROOT / "skills" / name / "SKILL.md"
        metadata, body = parse_frontmatter(path.read_text())
        assert metadata["name"] == name
        assert len(metadata["description"]) <= 60
        assert metadata["description"].endswith(".")
        assert len(body.splitlines()) <= 120
        for related in metadata["metadata"]["hermes"]["related_skills"]:
            assert (ROOT / "skills" / related / "SKILL.md").is_file()
    assert (ROOT / "skills/agent-operations/SKILL.md").resolve() == ROOT / "skills/use/SKILL.md"


def test_skill_references_are_present():
    use = ROOT / "skills/use"
    setup = ROOT / "skills/profile-setup"
    for relative in ("references/ntn.md", "references/page-authoring.md",
                     "references/block-types.md", "scripts/ntn_profile.py"):
        assert (use / relative).is_file()
    for relative in ("references/webhook-activation.md",
                     "references/listener-diagnostics.md", "references/maintenance.md"):
        assert (setup / relative).is_file()


def test_cli_environment_excludes_other_profile_and_redirects(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTION_API_TOKEN", "wrong-profile")
    monkeypatch.setenv("NOTION_API_TOKEN_AROA", "other-profile")
    monkeypatch.setenv("NOTION_HOME", "/shared-auth")
    monkeypatch.setenv("NOTION_API_BASE_URL", "https://untrusted.invalid")
    env = wrapper().cli_environment(tmp_path, "correct-profile")
    assert env["NOTION_API_TOKEN"] == "correct-profile"
    assert "NOTION_API_TOKEN_AROA" not in env
    assert env["NOTION_API_BASE_URL"] == "https://api.notion.com"
    assert env["NOTION_HOME"] == str(tmp_path / "plugin-data/notion/cli")
    assert env["NOTION_KEYRING"] == "0"


@pytest.mark.parametrize("args", [
    ["api", "https://untrusted.invalid/users/me"],
    ["api", "v1/../users/me"],
    ["login"], ["auth"], ["workers", "deploy"],
    ["api", "v1/users/me", "Authorization:Bearer unsafe"],
])
def test_unsupported_cli_calls_do_not_start_process(args, monkeypatch, capsys):
    mod = wrapper()
    monkeypatch.setattr(mod.subprocess, "run", lambda *_a, **_k: pytest.fail("must not run"))
    assert mod.main(args) == 2
    assert "unsafe" not in capsys.readouterr().err


def test_cli_binds_current_profile_and_resets_scope(monkeypatch, tmp_path, capsys):
    import agent.secret_scope as secrets
    import hermes_constants
    import hermes_notion.settings as settings
    mod = wrapper()
    calls = []
    monkeypatch.setattr(mod.shutil, "which", lambda name: "/installed/ntn")
    monkeypatch.setattr(hermes_constants, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr(secrets, "build_profile_secret_scope", lambda home: ("scope", home))
    monkeypatch.setattr(secrets, "set_multiplex_context", lambda value: "multi-marker")
    monkeypatch.setattr(secrets, "reset_multiplex_context", lambda marker: calls.append(("reset-multi", marker)))
    monkeypatch.setattr(secrets, "set_secret_scope", lambda scope, **kwargs: "scope-marker")
    monkeypatch.setattr(secrets, "reset_secret_scope", lambda marker: calls.append(("reset-scope", marker)))
    monkeypatch.setattr(settings.NotionSettings, "from_config", lambda: SimpleNamespace(token="private-token"))
    def run(args, env, check):
        assert args == ["/installed/ntn", "api", "v1/users/me"]
        assert env["NOTION_API_TOKEN"] == "private-token"
        assert env["NOTION_HOME"].startswith(str(tmp_path))
        return SimpleNamespace(returncode=7)
    monkeypatch.setattr(mod.subprocess, "run", run)
    assert mod.main(["api", "v1/users/me"]) == 7
    assert calls == [("reset-scope", "scope-marker"), ("reset-multi", "multi-marker")]
    assert "private-token" not in capsys.readouterr().out
