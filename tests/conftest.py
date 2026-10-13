import pytest


@pytest.fixture(autouse=True)
def isolated_plugin_home(tmp_path, monkeypatch):
    """Never touch operational state or signing secrets in tests."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
