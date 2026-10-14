import pytest


@pytest.fixture(autouse=True)
def no_network_receipts(monkeypatch):
    from hermes_notion import notion_client
    monkeypatch.setattr(notion_client, "create_acknowledgement", lambda **kw: {"id": "fixture-receipt"})
    monkeypatch.setattr(notion_client, "update_comment", lambda **kw: {"id": kw["comment_id"]})



@pytest.fixture(autouse=True)
def isolated_plugin_home(tmp_path, monkeypatch):
    """Never touch operational state or signing secrets in tests."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
