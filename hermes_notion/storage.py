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

def secrets_path() -> Path:
    return data_dir() / "secrets.json"

def get_verification_token() -> Optional[str]:
    env_val = os.getenv("NOTION_WEBHOOK_SECRET")
    if env_val:
        return env_val.strip()
    path = secrets_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return data.get("verification_token")
        except Exception as exc:
            logger.warning("[notion] Could not read secrets.json: %s", exc)
    return None

def save_verification_token(token: str) -> None:
    path = secrets_path()
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        data = {}
    data["verification_token"] = token
    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)
    logger.info("[notion] Saved verification token to secrets.json")
