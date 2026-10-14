"""Profile-scoped Notion comment tools. Other MCP/CLI tools are outside this boundary."""
from __future__ import annotations

from typing import Any, Dict
from hermes_cli.config import load_config
from . import notion_client, storage, policy
from .settings import NotionSettings

TOOLSET = "notion"
SCHEMAS = {
    "notion_ntn": {
        "name": "notion_ntn",
        "description": "Run NTN workspace CLI commands with the current profile only. Read/edit pages and blocks, create databases, query data sources and manage uploads. No shell/login/credential overrides. Use args=['api','v1/blocks/ID','-X','PATCH'] and body={...}; query parameters use name==value. Load notion:use, inspect endpoint --spec/--docs, and read back writes.",
        "parameters": {"type": "object", "properties": {
            "args": {"type": "array", "items": {"type": "string"}, "description": "NTN arguments without the executable. Supports api, pages, datasources, files, whoami and help."},
            "body": {"type": "object", "description": "Optional JSON body for api requests; no local input files."},
            "stdin": {"type": "string", "description": "Optional literal Markdown/text input for high-level commands, never a local file path."}},
            "required": ["args"]}},
    "notion_reply_comment": {
        "name": "notion_reply_comment",
        "description": "Reply to a bound, permitted Notion discussion; verifies readback.",
        "parameters": {"type": "object", "properties": {
            "discussion_id": {"type": "string"}, "content": {"type": "string"}},
            "required": ["discussion_id", "content"]}},
    "notion_get_comments": {
        "name": "notion_get_comments",
        "description": "List comments on a block/page within configured allowed roots.",
        "parameters": {"type": "object", "properties": {"block_id": {"type": "string"},
            "discussion_id": {"type": "string", "description": "Optional exact discussion filter."},
            "offset": {"type": "integer", "minimum": 0, "description": "Offset from previous next_offset; follow has_more until false."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
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
    if not parent_id:
        return {"ok": False, "error": "unbound_discussion"}

    gate = policy.check_mutation_gate(
        profile=settings.profile,
        token=token,
        target_id=parent_id,
        operation="reply_comment",
        allowed_root_ids=settings.allowed_root_ids,
        allowed_user_ids=settings.allowed_user_ids,
        issuer_user_id=kw.get("issuer_user_id"),
    )
    if not gate.allowed:
        return {"ok": False, "error": gate.reason}

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
    settings = _settings()
    if not policy.in_scope(token, block_id, settings.allowed_root_ids, profile=settings.profile):
        return {"ok": False, "error": "outside_allowed_roots"}
    try:
        offset, limit = args.get("offset", 0), args.get("limit", 20)
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 50:
            return {"ok": False, "error": "invalid_pagination"}
        from gateway.session_context import get_session_env
        if get_session_env("HERMES_SESSION_PLATFORM", "") == "notion":
            from .ntn import _current_request
            _current_request(settings)
        comments = notion_client.get_comments_for_block(token, block_id)
        if args.get("discussion_id"):
            comments = [c for c in comments if c.get("discussion_id") == args["discussion_id"]]
        selected = comments[offset:offset + limit]
        next_offset = offset + len(selected)
        return {"ok": True, "comments": selected, "total": len(comments),
                "has_more": next_offset < len(comments), "next_offset": next_offset if next_offset < len(comments) else None}
    except Exception:
        return {"ok": False, "error": "notion_request_failed"}


def ntn_command(args: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    from .ntn import execute
    return execute(args, _settings())


HANDLERS = {"notion_reply_comment": reply_comment, "notion_get_comments": get_comments, "notion_ntn": ntn_command}
