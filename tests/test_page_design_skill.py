"""Contract for the original, read-only Notion editorial design skill."""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock

from agent.skill_utils import parse_frontmatter

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/notion-page-design"


def test_design_entry_metadata_and_reviewed_references():
    text = (SKILL / "SKILL.md").read_text()
    metadata, body = parse_frontmatter(text)
    assert metadata["name"] == "notion-page-design"
    assert len(metadata["description"]) <= 60
    assert metadata["description"].endswith(".")
    assert "Notion" in metadata["description"]
    assert len(text.splitlines()) <= 100
    assert metadata["version"] == "0.1.0"
    assert metadata["license"] == "MIT"
    assert set(metadata["platforms"]) == {"linux", "macos", "windows"}
    assert metadata["author"].startswith("Koen ")
    for related in metadata["metadata"]["hermes"]["related_skills"]:
        assert (ROOT / "skills" / related / "SKILL.md").is_file()
    for name in ("modern-minimal.md", "demonstration.md"):
        relative = f"references/{name}"
        assert relative in body
        assert (SKILL / relative).read_text().strip()
    reference = (SKILL / "references/modern-minimal.md").read_text()
    assert "https://github.com/Percona-Lab/BINER/blob/HEAD/skills/notion-beautifier/SKILL.md" in reference
    assert "https://github.com/thelobbi/claude-m/blob/main/notion/skills/notion-mastery/references/page-design-patterns.md" in reference
    for requirement in ("knowledge-management", "notion:use", "native", "headings",
                        "callouts", "columns", "headers", "image", "toggles",
                        "reading order", "Preserve", "read back"):
        assert requirement in body


def test_technical_guide_routes_design_work_without_duplicating_it():
    text = (ROOT / "skills/use/SKILL.md").read_text()
    assert "notion:notion-page-design" in text
    assert "knowledge-management" in text


def test_plugin_registration_reaches_agent_and_desktop_catalog(monkeypatch):
    from hermes_cli import plugins
    from tools import skills_tool
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from hermes_cli.web_routers.skills import router

    manager = plugins.PluginManager()
    manifest = plugins.PluginManifest(name="notion", version="0.1.0")
    context = plugins.PluginContext(manifest, manager)
    # Register the real skills; omit unrelated platform/tool/hook registrations.
    context.register_hook = Mock()
    context.register_platform = Mock()
    context.register_tool = Mock()
    spec = importlib.util.spec_from_file_location(
        "design_test_plugin", ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    module.register(context)
    monkeypatch.setattr(plugins, "discover_plugins", lambda: None)
    monkeypatch.setattr(plugins, "get_plugin_manager", lambda: manager)
    name = "notion:notion-page-design"
    assert manager.find_plugin_skill(name) == SKILL / "SKILL.md"
    listed = json.loads(skills_tool.skills_list())
    assert name in {entry["name"] for entry in listed["skills"]}
    loaded = json.loads(skills_tool.skill_view(name))
    assert loaded["success"] is True
    assert "# Notion page design" in loaded["content"]
    for relative in ("references/modern-minimal.md", "references/demonstration.md"):
        assert json.loads(skills_tool.skill_view(name, file_path=relative))["success"] is True
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        result = client.get("/api/skills")
        assert result.status_code == 200
        entries = [entry for entry in result.json() if entry["name"] == name]
        assert len(entries) == 1
        assert entries[0]["read_only"] is True
        assert entries[0]["enabled"] is True
        assert entries[0]["provenance"] == "plugin"
        assert entries[0]["description"] == parse_frontmatter((SKILL / "SKILL.md").read_text())[0]["description"]
        content = client.get("/api/skills/content", params={"name": name})
        assert content.status_code == 200
        assert content.json()["content"] == (SKILL / "SKILL.md").read_text()
