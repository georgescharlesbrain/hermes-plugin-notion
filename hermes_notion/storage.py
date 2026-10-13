from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def data_dir() -> Path:
    from hermes_constants import get_hermes_home
    home = get_hermes_home()
    target = home / "plugin-data" / "notion"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _db_connection() -> sqlite3.Connection:
    path = data_dir() / "replay.db"
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    os.chmod(path, 0o600)
    with db:
        db.execute("CREATE TABLE IF NOT EXISTS processed (comment_id TEXT PRIMARY KEY)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS discussions (
                discussion_id TEXT PRIMARY KEY,
                owner TEXT,
                parent_id TEXT,
                stopped INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS reply_reservations (
                reservation_id TEXT PRIMARY KEY,
                discussion_id TEXT,
                reserved_at REAL,
                committed INTEGER DEFAULT 0
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS turn_replies (
                turn_id TEXT PRIMARY KEY,
                reply_count INTEGER DEFAULT 0,
                updated_at REAL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS provisioning_tickets (
                ticket_id TEXT PRIMARY KEY,
                profile TEXT,
                subscription_id TEXT,
                created_at REAL,
                expires_at REAL,
                consumed INTEGER DEFAULT 0,
                allow_replacement INTEGER DEFAULT 0
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS circuit_breaker_tripped (
                discussion_id TEXT PRIMARY KEY,
                tripped INTEGER DEFAULT 0,
                tripped_at REAL
            )
        """)
    return db


def secrets_path(profile: str = "greta") -> Path:
    filename = "secrets.json" if profile == "greta" else f"secrets_{profile}.json"
    return data_dir() / filename


def get_verification_token(profile: str = "greta") -> Optional[str]:
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


# --- Provisioning Tickets (Authenticated Expiring Handshakes) ---

def create_provisioning_ticket(
    profile: str,
    subscription_id: str,
    ttl_seconds: int = 300,
    allow_replacement: bool = False,
) -> Dict[str, Any]:
    ticket_id = secrets.token_hex(16)
    now = time.time()
    expires_at = now + ttl_seconds
    db = _db_connection()
    try:
        with db:
            db.execute(
                """
                INSERT INTO provisioning_tickets
                (ticket_id, profile, subscription_id, created_at, expires_at, consumed, allow_replacement)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (ticket_id, profile, subscription_id, now, expires_at, 1 if allow_replacement else 0),
            )
    finally:
        db.close()
    return {
        "ticket_id": ticket_id,
        "profile": profile,
        "subscription_id": subscription_id,
        "created_at": now,
        "expires_at": expires_at,
        "allow_replacement": allow_replacement,
    }


def claim_provisioning_ticket(
    ticket_id: str,
    profile: str,
    subscription_id: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    if not ticket_id:
        return False, "missing ticket_id", None
    db = _db_connection()
    try:
        with db:
            row = db.execute(
                "SELECT * FROM provisioning_tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if not row:
                return False, "provisioning ticket not found", None
            if row["consumed"]:
                return False, "provisioning ticket already consumed", None
            now = time.time()
            if now > row["expires_at"]:
                return False, "provisioning ticket expired", None
            if row["profile"] != profile:
                return False, "ticket profile mismatch", None
            if row["subscription_id"] != subscription_id:
                return False, "subscription mismatch", None
            # Check replacement policy
            if not row["allow_replacement"] and get_verification_token(profile) is not None:
                return False, "unauthorized secret replacement denied", None
            db.execute(
                "UPDATE provisioning_tickets SET consumed = 1 WHERE ticket_id = ?", (ticket_id,)
            )
            return True, "ok", dict(row)
    finally:
        db.close()


# --- Durable Discussion Ownership & Parent Tracking ---

def discussions_path() -> Path:
    return data_dir() / "discussions.json"


def get_discussion_owner(discussion_id: str) -> Optional[str]:
    if not discussion_id:
        return None
    db = _db_connection()
    try:
        row = db.execute(
            "SELECT owner, stopped FROM discussions WHERE discussion_id = ?", (discussion_id,)
        ).fetchone()
        if row:
            if row["stopped"]:
                return "stopped"
            return row["owner"]
    finally:
        db.close()
    # Legacy fallback
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
    now = time.time()
    is_stopped = 1 if bot_name.lower() == "stopped" else 0
    normalized_owner = bot_name.lower()
    db = _db_connection()
    try:
        with db:
            db.execute(
                """
                INSERT INTO discussions (discussion_id, owner, stopped, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(discussion_id) DO UPDATE SET
                    owner = excluded.owner,
                    stopped = excluded.stopped,
                    updated_at = excluded.updated_at
                """,
                (discussion_id, normalized_owner, is_stopped, now, now),
            )
    finally:
        db.close()
    # Legacy JSON mirror for compatibility
    path = discussions_path()
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        data = {}
    data[discussion_id] = normalized_owner
    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)


def get_discussion_parent(discussion_id: str) -> Optional[str]:
    if not discussion_id:
        return None
    db = _db_connection()
    try:
        row = db.execute(
            "SELECT parent_id FROM discussions WHERE discussion_id = ?", (discussion_id,)
        ).fetchone()
        if row and row["parent_id"]:
            return row["parent_id"]
    finally:
        db.close()
    path = data_dir() / "discussion_parents.json"
    try:
        return json.loads(path.read_text()).get(discussion_id)
    except (OSError, ValueError):
        return None


def set_discussion_parent(discussion_id: str, parent_id: str) -> None:
    if not discussion_id or not parent_id:
        return
    now = time.time()
    db = _db_connection()
    try:
        with db:
            db.execute(
                """
                INSERT INTO discussions (discussion_id, parent_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(discussion_id) DO UPDATE SET
                    parent_id = excluded.parent_id,
                    updated_at = excluded.updated_at
                """,
                (discussion_id, parent_id, now, now),
            )
    finally:
        db.close()
    path = data_dir() / "discussion_parents.json"
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        data = {}
    data[discussion_id] = parent_id
    path.write_text(json.dumps(data))
    os.chmod(path, 0o600)


# --- Idempotency / Deduplication Cache ---

def dedup_path() -> Path:
    return data_dir() / "processed_comments.json"


def claim_comment(comment_id: str) -> bool:
    if not comment_id:
        return False
    if is_comment_processed(comment_id):
        return False
    db = _db_connection()
    try:
        with db:
            result = db.execute("INSERT OR IGNORE INTO processed VALUES (?)", (comment_id,))
        return result.rowcount == 1
    finally:
        db.close()


def is_comment_processed(comment_id: str) -> bool:
    if not comment_id:
        return False
    db = _db_connection()
    try:
        if db.execute("SELECT 1 FROM processed WHERE comment_id = ?", (comment_id,)).fetchone():
            return True
    finally:
        db.close()
    path = dedup_path()
    if path.exists():
        try:
            return comment_id in json.loads(path.read_text())
        except (OSError, ValueError):
            raise RuntimeError("invalid legacy replay state")
    return False


def mark_comment_processed(comment_id: str) -> None:
    if not comment_id:
        return
    db = _db_connection()
    try:
        with db:
            db.execute("INSERT OR IGNORE INTO processed VALUES (?)", (comment_id,))
    finally:
        db.close()


# --- Atomic Reply Reservations & Circuit Breaker ---

def circuit_breaker_path() -> Path:
    return data_dir() / "circuit_breaker.json"


def reserve_reply_slot(
    discussion_id: str,
    cooldown_seconds: float = 3.0,
    max_replies: int = 5,
    window_seconds: float = 60.0,
) -> Tuple[bool, str, Optional[str]]:
    if not discussion_id:
        return True, "ok", None
    now = time.time()
    db = _db_connection()
    try:
        with db:
            # 1. Check if discussion is stopped
            row_disc = db.execute(
                "SELECT stopped FROM discussions WHERE discussion_id = ?", (discussion_id,)
            ).fetchone()
            if row_disc and row_disc["stopped"]:
                return False, "discussion_stopped", None

            # 2. Check permanent trip state
            row_tripped = db.execute(
                "SELECT tripped FROM circuit_breaker_tripped WHERE discussion_id = ?", (discussion_id,)
            ).fetchone()
            if row_tripped and row_tripped["tripped"]:
                return False, "circuit_breaker_tripped", None

            # 3. Query active/committed reservations within window
            window_start = now - window_seconds
            # Clean up ancient reservations older than 1 hour
            db.execute(
                "DELETE FROM reply_reservations WHERE reserved_at < ?", (now - 3600.0,)
            )
            rows = db.execute(
                """
                SELECT reserved_at FROM reply_reservations
                WHERE discussion_id = ?
                  AND reserved_at >= ?
                  AND (committed = 1 OR reserved_at >= ?)
                ORDER BY reserved_at ASC
                """,
                (discussion_id, window_start, now - 15.0),
            ).fetchall()
            recent_timestamps = [r["reserved_at"] for r in rows]

            # 4. Check minimum interval cooldown
            if recent_timestamps:
                last_reply = recent_timestamps[-1]
                if now - last_reply < cooldown_seconds:
                    return False, "thread_cooldown_active", None

            # 5. Check sliding window velocity limit
            if len(recent_timestamps) >= max_replies:
                db.execute(
                    "INSERT OR REPLACE INTO circuit_breaker_tripped (discussion_id, tripped, tripped_at) VALUES (?, 1, ?)",
                    (discussion_id, now),
                )
                logger.error("[notion] Velocity circuit breaker TRIPPED for %s (%d replies in %ds)",
                             discussion_id, len(recent_timestamps), int(window_seconds))
                return False, "velocity_breaker_tripped", None

            # 6. Allocate atomic reservation
            reservation_id = secrets.token_hex(16)
            db.execute(
                "INSERT INTO reply_reservations (reservation_id, discussion_id, reserved_at, committed) VALUES (?, ?, ?, 0)",
                (reservation_id, discussion_id, now),
            )
            return True, "ok", reservation_id
    finally:
        db.close()


def commit_reply_reservation(reservation_id: str) -> None:
    if not reservation_id:
        return
    db = _db_connection()
    try:
        with db:
            db.execute(
                "UPDATE reply_reservations SET committed = 1 WHERE reservation_id = ?", (reservation_id,)
            )
    finally:
        db.close()


def rollback_reply_reservation(reservation_id: str) -> None:
    if not reservation_id:
        return
    db = _db_connection()
    try:
        with db:
            db.execute(
                "DELETE FROM reply_reservations WHERE reservation_id = ? AND committed = 0", (reservation_id,)
            )
    finally:
        db.close()


def check_circuit_breaker(
    discussion_id: str,
    cooldown_seconds: float = 3.0,
    max_replies: int = 5,
    window_seconds: float = 60.0,
) -> Tuple[bool, str]:
    allowed, reason, _ = reserve_reply_slot(discussion_id, cooldown_seconds, max_replies, window_seconds)
    return allowed, reason


def record_bot_reply(discussion_id: str) -> None:
    if not discussion_id:
        return
    now = time.time()
    db = _db_connection()
    try:
        with db:
            res_id = secrets.token_hex(16)
            db.execute(
                "INSERT INTO reply_reservations (reservation_id, discussion_id, reserved_at, committed) VALUES (?, ?, ?, 1)",
                (res_id, discussion_id, now),
            )
    finally:
        db.close()


def reset_circuit_breaker(discussion_id: str) -> None:
    if not discussion_id:
        return
    db = _db_connection()
    try:
        with db:
            db.execute(
                "DELETE FROM circuit_breaker_tripped WHERE discussion_id = ?", (discussion_id,)
            )
            db.execute(
                "DELETE FROM reply_reservations WHERE discussion_id = ?", (discussion_id,)
            )
    finally:
        db.close()


# --- Per-turn reply budget tracking ---

def claim_turn_reply(turn_id: str, max_replies: int = 2) -> Tuple[bool, str]:
    if not turn_id:
        return True, "ok"
    now = time.time()
    db = _db_connection()
    try:
        with db:
            row = db.execute(
                "SELECT reply_count FROM turn_replies WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            count = row["reply_count"] if row else 0
            if count >= max_replies:
                return False, "turn_reply_budget_exceeded"
            db.execute(
                """
                INSERT INTO turn_replies (turn_id, reply_count, updated_at)
                VALUES (?, 1, ?)
                ON CONFLICT(turn_id) DO UPDATE SET
                    reply_count = reply_count + 1,
                    updated_at = excluded.updated_at
                """,
                (turn_id, now),
            )
            return True, "ok"
    finally:
        db.close()
