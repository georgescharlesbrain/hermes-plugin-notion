"""Run workspace ntn commands with only the current profile's credential."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import re
import sys

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

ALLOWED_COMMANDS = {"api", "pages", "datasources", "files"}


def cli_environment(home: Path, token: str) -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("NOTION_"):
            env.pop(key)
    env.update({
        "NOTION_API_TOKEN": token,
        "NOTION_API_BASE_URL": "https://api.notion.com",
        "NOTION_API_DOCS_BASE_URL": "https://developers.notion.com",
        "NOTION_ENV": "prod",
        "NOTION_HOME": str(home / "plugin-data" / "notion" / "cli"),
        "NOTION_KEYRING": "0",
    })
    return env


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("Usage: ntn_profile.py {api,pages,datasources,files} [ntn arguments]")
        print("Uses the active Hermes profile; never pass a token.")
        return 0
    if argv[0] not in ALLOWED_COMMANDS or any(
        arg.lower().startswith("authorization:") for arg in argv
    ):
        print("Unsupported command or credential override.", file=sys.stderr)
        return 2
    if argv[0] == "api" and len(argv) > 1 and argv[1] not in {"ls", "-h", "--help", "help"}:
        endpoint = argv[1]
        if not re.fullmatch(r"/?v1/[A-Za-z0-9_/-]+", endpoint):
            print("Use a relative v1 API endpoint, not a URL or path override.", file=sys.stderr)
            return 2

    executable = shutil.which("ntn")
    if not executable:
        print("ntn is not installed.", file=sys.stderr)
        return 2

    from agent.secret_scope import (
        build_profile_secret_scope, set_secret_scope, reset_secret_scope,
        set_multiplex_context, reset_multiplex_context,
    )
    from hermes_constants import get_hermes_home
    from hermes_notion.settings import NotionSettings

    home = Path(get_hermes_home())
    multi = set_multiplex_context(True)
    scope = None
    try:
        scope = set_secret_scope(build_profile_secret_scope(home), profile_home=str(home))
        settings = NotionSettings.from_config()
        if not settings.token:
            print("No Notion API token for the active profile.", file=sys.stderr)
            return 2
        return subprocess.run(
            [executable, *argv], env=cli_environment(home, settings.token),
            check=False,
        ).returncode
    finally:
        if scope is not None:
            reset_secret_scope(scope)
        reset_multiplex_context(multi)


if __name__ == "__main__":
    raise SystemExit(main())
