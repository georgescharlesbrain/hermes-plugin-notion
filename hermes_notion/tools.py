"""Profile-scoped Notion comment tools. Other MCP/CLI tools are outside this boundary."""
from __future__ import annotations

from typing import Any, Dict
from hermes_cli.config import load_config
from . import notion_client, storage, policy
from .settings import NotionSettings

TOOLSET = "notion"
SCHEMAS = {
    "notion_reply_comment": {
        "name": "notion_reply_comment",
        "description": "Reply to a bound, permitted Notion discussion; verifies readback.",
        "parameters": {"type": "object", "properties": {
            "discussion_id": {"type": "string"}, "content": {"type": "string"}},
            "required": ["discussion_id", "content"]}},
    "notion_get_comments": {
        "name": "notion_get_comments",
        "description": "List comments on a block/page within configured allowed roots.",
        "parameters": {"type": "object", "properties": {"block_id": {"type": "string"}},
                       "required": ["block_id"]}},
}


def _settings():
    config = load_config()
    extra = ((config.get("platforms") or {}).get("notion") or {})
    return NotionSettings.from_config(extra.get("extra", extra))


def _load_token() -> str:
    return _settings().token.strip()


def check_requirements() -> bool:
    return bool(_load_token())


def reply_comment(args: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    settings = _settings()
    token = _load_token()
    if not token:
        return {"ok": False, "error": "notion_not_configured"}
    discussion_id = args.get("discussion_id", "")
    content = args.get("content", "")
    if storage.get_discussion_owner(discussion_id) != settings.profile:
        return {"ok": False, "error": "unbound_discussion"}
    parent_id = storage.get_discussion_parent(discussion_id)
    if not policy.in_scope(token, parent_id, settings.allowed_root_ids):
        return {"ok": False, "error": "outside_allowed_roots"}
    allowed, reason = storage.check_circuit_breaker(discussion_id)
    if not allowed:
        return {"ok": False, "error": reason}
    try:
        res = notion_client.create_comment_reply(token, discussion_id, content)
        storage.record_bot_reply(discussion_id)
        verified = notion_client.get_comment(token, res.get("id", ""))
        if verified.get("discussion_id") != discussion_id:
            return {"ok": False, "error": "reply_readback_mismatch"}
        return {"ok": True, "comment_id": res.get("id")}
    except Exception:
        return {"ok": False, "error": "notion_request_failed"}


def get_comments(args: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    token = _load_token()
    if not token:
        return {"ok": False, "error": "notion_not_configured"}
    block_id = args.get("block_id", "")
    if not policy.in_scope(token, block_id, _settings().allowed_root_ids):
        return {"ok": False, "error": "outside_allowed_roots"}
    try:
        return {"ok": True, "comments": notion_client.get_comments_for_block(token, block_id)}
    except Exception:
        return {"ok": False, "error": "notion_request_failed"}


HANDLERS = {"notion_reply_comment": reply_comment, "notion_get_comments": get_comments}
