"""Notion tools for Hermes."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from . import notion_client

logger = logging.getLogger(__name__)

TOOLSET = "notion"

SCHEMAS: Dict[str, Dict[str, Any]] = {
    "notion_reply_comment": {
        "name": "notion_reply_comment",
        "description": "Post a reply comment to an existing Notion discussion thread.",
        "parameters": {
            "type": "object",
            "properties": {
                "discussion_id": {
                    "type": "string",
                    "description": "The Notion discussion UUID to reply to.",
                },
                "content": {
                    "type": "string",
                    "description": "The text content for the reply comment.",
                },
            },
            "required": ["discussion_id", "content"],
        },
    },
    "notion_get_comments": {
        "name": "notion_get_comments",
        "description": "List comments attached to a Notion block or page.",
        "parameters": {
            "type": "object",
            "properties": {
                "block_id": {
                    "type": "string",
                    "description": "The Notion block or page UUID.",
                },
            },
            "required": ["block_id"],
        },
    },
}

def check_requirements() -> bool:
    token = os.getenv("NOTION_API_TOKEN") or os.getenv("NOTION_API_KEY")
    return bool(token and token.strip())

def _load_token() -> str:
    token = os.getenv("NOTION_API_TOKEN") or os.getenv("NOTION_API_KEY") or ""
    return token.strip()

def reply_comment(args: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    token = _load_token()
    if not token:
        return {"ok": False, "error": "NOTION_API_TOKEN is not configured"}
    discussion_id = args.get("discussion_id", "")
    content = args.get("content", "")
    try:
        res = notion_client.create_comment_reply(token, discussion_id, content)
        return {"ok": True, "comment_id": res.get("id")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def get_comments(args: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    token = _load_token()
    if not token:
        return {"ok": False, "error": "NOTION_API_TOKEN is not configured"}
    block_id = args.get("block_id", "")
    try:
        res = notion_client.get_comments_for_block(token, block_id)
        return {"ok": True, "comments": res}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

HANDLERS = {
    "notion_reply_comment": reply_comment,
    "notion_get_comments": get_comments,
}
