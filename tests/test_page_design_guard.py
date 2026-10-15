"""Design guidance is readable only in owned default-profile Notion turns."""
import pytest

from hermes_notion import guard, storage

NAME = "notion:notion-page-design"


def setup_turn(monkeypatch, tmp_path, profile="default", named_home=False, owner="aroa"):
    env = {"HERMES_SESSION_PLATFORM": "notion", "HERMES_SESSION_THREAD_ID": "design-thread",
           "HERMES_SESSION_PROFILE": profile}
    monkeypatch.setattr(guard, "get_session_env", lambda key, default="": env.get(key, default))
    home = tmp_path / "profiles" / "greta" if named_home else tmp_path
    monkeypatch.setattr(guard, "get_hermes_home", lambda: home)
    if owner:
        storage.set_discussion_owner("design-thread", owner)


def call(args, wrapped):
    if wrapped:
        return guard.check("tool_call", {"calls": [{"name": "skill_view", "arguments": args}]})
    return guard.check("skill_view", args)


@pytest.mark.parametrize("file_path", [None, "", "references/modern-minimal.md", "references/demonstration.md"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_default_owned_turn_can_read_design_guidance(monkeypatch, tmp_path, file_path, wrapped):
    setup_turn(monkeypatch, tmp_path)
    assert call({"name": NAME, "file_path": file_path}, wrapped) is None


@pytest.mark.parametrize("file_path", ["/etc/passwd", "../SKILL.md", "references/../../.env",
    "references/../modern-minimal.md", "references\\modern-minimal.md", "references/unknown.md",
    "references/workspace.md", "scripts/run.py", "SKILL.md", [], {}, 42, False, True])
@pytest.mark.parametrize("wrapped", [False, True])
def test_design_guidance_rejects_every_non_allowlisted_file(monkeypatch, tmp_path, file_path, wrapped):
    setup_turn(monkeypatch, tmp_path)
    assert call({"name": NAME, "file_path": file_path}, wrapped)["action"] == "block"


@pytest.mark.parametrize("profile,named_home", [("greta", True), ("aroa", True),
    ("default", True), ("greta", False), ("", False)])
@pytest.mark.parametrize("wrapped", [False, True])
def test_design_guidance_does_not_expand_named_profile_permissions(monkeypatch, tmp_path, profile, named_home, wrapped):
    setup_turn(monkeypatch, tmp_path, profile, named_home, owner=profile)
    assert call({"name": NAME}, wrapped)["action"] == "block"


@pytest.mark.parametrize("owner", ["stopped", "greta", None])
@pytest.mark.parametrize("wrapped", [False, True])
def test_design_guidance_still_requires_owned_discussion(monkeypatch, tmp_path, owner, wrapped):
    setup_turn(monkeypatch, tmp_path, owner=owner)
    assert call({"name": NAME}, wrapped)["action"] == "block"


@pytest.mark.parametrize("name", ["notion-page-design", "notion:other-design", "../notion-page-design"])
def test_design_allowlist_does_not_admit_other_names(monkeypatch, tmp_path, name):
    setup_turn(monkeypatch, tmp_path)
    assert call({"name": name}, False)["action"] == "block"


@pytest.mark.parametrize("name", ["notion:use", "notion:profile-setup"])
def test_existing_named_profile_plugin_guidance_is_unchanged(monkeypatch, tmp_path, name):
    setup_turn(monkeypatch, tmp_path, "greta", True, "greta")
    assert call({"name": name}, False) is None
