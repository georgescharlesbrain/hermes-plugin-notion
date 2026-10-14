"""Bounded ancestry checks, strict identifier validation, and common mutation gate."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Set

from . import notion_client
from .settings import valid_profile_name

NOTION_UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)

SAFE_IDENTIFIER_REGEX = re.compile(r"^[0-9a-zA-Z_-]+$")

SUPPORTED_PARENT_TYPES = {"page_id", "block_id", "database_id", "data_source_id"}


@dataclass
class MutationDecision:
    allowed: bool
    reason: str
    target_id: Optional[str] = None
    operation: str = ""
    profile: str = ""


def is_strict_notion_id(identifier: Any) -> bool:
    if not isinstance(identifier, str):
        return False
    clean = identifier.strip()
    return bool(NOTION_UUID_REGEX.match(clean))


def is_valid_identifier(identifier: Any) -> bool:
    if not isinstance(identifier, str) or not identifier:
        return False
    clean = identifier.strip()
    return bool(SAFE_IDENTIFIER_REGEX.match(clean))


def normalize_identifier(identifier: str) -> str:
    clean = identifier.strip()
    if is_strict_notion_id(clean):
        raw = clean.replace("-", "").lower()
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
    return clean.lower()


def in_scope(token: str, target_id: str, root_ids: List[str], profile: str = "greta") -> bool:
    if not token or not target_id or not root_ids:
        return False
    if not is_valid_identifier(target_id):
        return False

    normalized_roots: Set[str] = set()
    for rid in root_ids:
        if rid == "*":
            normalized_roots.add("*")
        elif rid == "workspace":
            normalized_roots.add("workspace")
        elif is_valid_identifier(rid):
            normalized_roots.add(normalize_identifier(rid))
        else:
            return False

    if "*" in normalized_roots:
        return True

    norm_target = normalize_identifier(target_id)
    seen: Set[str] = set()
    current_id = norm_target

    for _ in range(32):
        if current_id in normalized_roots:
            return True
        if current_id in seen:
            return False
        seen.add(current_id)

        try:
            obj = notion_client.get_container(token, current_id)
        except Exception:
            return False

        if not isinstance(obj, dict):
            return False

        parent = obj.get("parent")
        if not isinstance(parent, dict):
            return False

        parent_type = parent.get("type")
        if not isinstance(parent_type, str):
            return False

        if parent_type == "workspace":
            return "workspace" in normalized_roots

        if parent_type in SUPPORTED_PARENT_TYPES:
            raw_parent_id = parent.get(parent_type)
            if not raw_parent_id and parent_type == "data_source_id":
                raw_parent_id = parent.get("database_id")
            if not isinstance(raw_parent_id, str) or not is_valid_identifier(raw_parent_id):
                return False
            current_id = normalize_identifier(raw_parent_id)
        else:
            # Fail closed on unknown or unsupported ancestry types
            return False

    return False


def check_mutation_gate(
    profile: str,
    token: str,
    target_id: str,
    operation: str,
    allowed_root_ids: List[str],
    allowed_user_ids: Optional[List[str]] = None,
    issuer_user_id: Optional[str] = None,
    allow_workspace_access: Optional[bool] = None,
) -> MutationDecision:
    """Common mutation gate across all plugin write tools."""
    if not valid_profile_name(profile):
        return MutationDecision(False, "unsupported_profile", target_id, operation, profile)

    if not token or not token.strip():
        return MutationDecision(False, "missing_token", target_id, operation, profile)

    if not is_valid_identifier(target_id):
        return MutationDecision(False, "invalid_target_identifier", target_id, operation, profile)

    if issuer_user_id is not None:
        if not allowed_user_ids or issuer_user_id not in allowed_user_ids:
            return MutationDecision(False, "unauthorized_human_issuer", target_id, operation, profile)

    supported_ops = {"reply_comment", "write_comment", "create_reply", "update", "delete"}
    if operation not in supported_ops:
        return MutationDecision(False, "unsupported_operation", target_id, operation, profile)

    # Production callers pass configured authority. The default preserves old direct API callers.
    workspace_allowed = profile == "aroa" if allow_workspace_access is None else allow_workspace_access
    if any(root in {"*", "workspace"} for root in allowed_root_ids) and not workspace_allowed:
        return MutationDecision(False, "wildcard_forbidden_for_profile", target_id, operation, profile)
    if not allowed_root_ids:
        return MutationDecision(False, "outside_allowed_roots", target_id, operation, profile)
    if in_scope(token, target_id, allowed_root_ids, profile=profile):
        reason = "authorized_workspace_authority" if "*" in allowed_root_ids else "authorized_in_scope"
        return MutationDecision(True, reason, target_id, operation, profile)
    return MutationDecision(False, "outside_allowed_roots", target_id, operation, profile)
