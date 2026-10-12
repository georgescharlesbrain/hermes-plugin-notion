from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

# --- Thread / Discussion Ownership ---

def discussions_path() -> Path:
    return data_dir() / "discussions.json"

def get_discussion_owner(discussion_id: str) -> Optional[str]:
    if not discussion_id:
        return None
    path = discussions_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return data.get(discussion_id)
        except Exception as exc:
            logger.warning("[notion] Could not read %s: %s", path.name, exc)
    return None

def set_discussion_owner(discussion_id: str, bot_name: str) -> None:
    if not discussion_id or not bot_name:
        return
    path = discussions_path()
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        data = {}
    data[discussion_id] = bot_name.lower()
    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)
    logger.info("[notion] Saved discussion owner for %s -> %s", discussion_id, bot_name)

# --- Idempotency / Deduplication Cache ---

def dedup_path() -> Path:
    return data_dir() / "processed_comments.json"

def is_comment_processed(comment_id: str) -> bool:
    if not comment_id:
        return False
    path = dedup_path()
    if path.exists():
        try:
            items = json.loads(path.read_text())
            return comment_id in set(items)
        except Exception:
            return False
    return False

def mark_comment_processed(comment_id: str) -> None:
    if not comment_id:
        return
    path = dedup_path()
    try:
        items = json.loads(path.read_text()) if path.exists() else []
    except Exception:
        items = []
    if comment_id not in items:
        items.append(comment_id)
        # Retain last 1000 items to bound storage
        if len(items) > 1000:
            items = items[-1000:]
        path.write_text(json.dumps(items, indent=2))
        os.chmod(path, 0o600)

# --- Circuit Breaker & Cooldown ---

def circuit_breaker_path() -> Path:
    return data_dir() / "circuit_breaker.json"

def check_circuit_breaker(
    discussion_id: str,
    cooldown_seconds: float = 3.0,
    max_replies: int = 5,
    window_seconds: float = 60.0
) -> Tuple[bool, str]:
    """
    Check if a reply to discussion_id is permitted.
    Returns (allowed, reason).
    """
    if not discussion_id:
        return True, "ok"

    path = circuit_breaker_path()
    if not path.exists():
        return True, "ok"

    try:
        data = json.loads(path.read_text())
    except Exception:
        return True, "ok"

    info = data.get(discussion_id)
    if not info:
        return True, "ok"

    # 1. Permanent trip check until reset
    if info.get("tripped"):
        return False, "circuit_breaker_tripped"

    replies = info.get("replies", [])
    now = time.time()

    # 2. Minimum interval cooldown
    if replies:
        last_reply = replies[-1]
        if now - last_reply < cooldown_seconds:
            return False, "thread_cooldown_active"

    # 3. Sliding window velocity
    recent = [ts for ts in replies if now - ts < window_seconds]
    if len(recent) >= max_replies:
        info["tripped"] = True
        try:
            path.write_text(json.dumps(data, indent=2))
        except Exception:
            pass
        logger.error("[notion] Velocity circuit breaker TRIPPED for discussion %s (%d replies in %ds)",
                     discussion_id, len(recent), int(window_seconds))
        return False, "velocity_breaker_tripped"

    return True, "ok"

def record_bot_reply(discussion_id: str) -> None:
    """Record a timestamped bot reply on a discussion thread."""
    if not discussion_id:
        return
    path = circuit_breaker_path()
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        data = {}

    info = data.setdefault(discussion_id, {"replies": [], "tripped": False})
    now = time.time()
    info["replies"].append(now)
    # Retain timestamps from last 1 hour
    info["replies"] = [ts for ts in info["replies"] if now - ts < 3600.0]

    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)

def reset_circuit_breaker(discussion_id: str) -> None:
    """Manually reset the circuit breaker for a discussion thread."""
    if not discussion_id:
        return
    path = circuit_breaker_path()
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        if discussion_id in data:
            data[discussion_id]["tripped"] = False
            data[discussion_id]["replies"] = []
            path.write_text(json.dumps(data, indent=2))
            logger.info("[notion] Reset circuit breaker for discussion %s", discussion_id)
    except Exception as exc:
        logger.warning("[notion] Could not reset circuit breaker: %s", exc)
