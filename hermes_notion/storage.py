from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def data_dir() -> Path:
    home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    target = home / "plugin-data" / "notion"
    target.mkdir(parents=True, exist_ok=True)
    return target

def secrets_path(profile: str = "greta") -> Path:
    filename = "secrets.json" if profile == "greta" else f"secrets_{profile}.json"
    return data_dir() / filename

def get_verification_token(profile: str = "greta") -> Optional[str]:
    env_var = "NOTION_WEBHOOK_SECRET" if profile == "greta" else f"NOTION_WEBHOOK_SECRET_{profile.upper()}"
    env_val = os.getenv(env_var)
    if env_val:
        return env_val.strip()
    path = secrets_path(profile)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return data.get("verification_token")
        except Exception as exc:
            logger.warning("[notion] Could not read %s: %s", path.name, exc)
    return None

def save_verification_token(token: str, profile: str = "greta", path_str: str = "") -> None:
    path = secrets_path(profile)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        data = {}
    data["verification_token"] = token
    if path_str:
        data["path"] = path_str
    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)
    logger.info("[notion] Saved verification token for %s to %s", profile, path.name)
