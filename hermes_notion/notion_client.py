from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
API_BASE = "https://api.notion.com/v1"

class NotionClientError(Exception):
    def __init__(self, status: int, message: str, code: str = ""):
        super().__init__(f"Notion API error {status}: {message} ({code})")
        self.status = status
        self.message = message
        self.code = code

def _request(token: str, path: str, method: str = "GET", data: Optional[Dict[str, Any]] = None, *, version: str = NOTION_VERSION) -> Dict[str, Any]:
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": version,
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("message", err_body)
            code = err_json.get("code", "")
        except Exception:
            msg, code = err_body, ""
        logger.error("[notion] HTTP request failed with status %d", err.code)
        raise NotionClientError(err.code, "request_failed") from None
    except Exception:
        logger.error("[notion] Request failed")
        raise NotionClientError(0, "request_failed") from None

def get_comment(token: str, comment_id: str) -> Dict[str, Any]:
    return _request(token, f"/comments/{comment_id}", method="GET")

def get_comments_for_block(token: str, block_id: str) -> List[Dict[str, Any]]:
    from urllib.parse import urlencode
    results = []
    cursor = None
    seen = set()
    for _ in range(100):
        params = {"block_id": block_id, "page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        res = _request(token, "/comments?" + urlencode(params), method="GET")
        results.extend(res.get("results", []))
        if not res.get("has_more"):
            return results
        cursor = res.get("next_cursor")
        if not cursor or cursor in seen:
            raise NotionClientError(502, "invalid pagination")
        seen.add(cursor)
    raise NotionClientError(502, "pagination budget exceeded")

def get_page(token: str, page_id: str) -> Dict[str, Any]:
    return _request(token, f"/pages/{page_id}", method="GET")

def get_block(token: str, block_id: str) -> Dict[str, Any]:
    return _request(token, f"/blocks/{block_id}", method="GET")

def extract_block_text(block: Dict[str, Any]) -> str:
    """Extract plain text content from a Notion block."""
    if not isinstance(block, dict):
        return ""
    btype = block.get("type", "")
    type_obj = block.get(btype, {})
    if isinstance(type_obj, dict):
        rich_text = type_obj.get("rich_text", [])
        if isinstance(rich_text, list):
            parts = [item.get("plain_text", "") for item in rich_text if isinstance(item, dict)]
            return "".join(parts).strip()
    return ""

def create_acknowledgement(token: str, discussion_id: str, content: str) -> Dict[str, Any]:
    """Fixed-text receipt. Never called by the model."""
    return create_comment_reply(token, discussion_id, content)


def update_comment(token: str, comment_id: str, content: str) -> Dict[str, Any]:
    chunks = [{"type": "text", "text": {"content": content[i:i + 1900]}}
              for i in range(0, len(content), 1900)]
    if not chunks:
        chunks = [{"type": "text", "text": {"content": " "}}]
    if len(chunks) > 100:
        raise NotionClientError(400, "comment_too_long")
    # Updating comments is available in this version. Keep existing reads unchanged.
    return _request(token, f"/comments/{comment_id}", method="PATCH",
                    data={"rich_text": chunks}, version="2026-03-11")


def create_comment_reply(token: str, discussion_id: str, content: str) -> Dict[str, Any]:
    # Chunk content if necessary (Notion limit is 2000 chars per text block)
    chunks = []
    max_chunk = 1900
    for i in range(0, len(content), max_chunk):
        chunks.append({
            "type": "text",
            "text": {"content": content[i:i + max_chunk]}
        })
    if not chunks:
        chunks = [{"type": "text", "text": {"content": " "}}]
        
    payload = {
        "discussion_id": discussion_id,
        "rich_text": chunks
    }
    return _request(token, "/comments", method="POST", data=payload)
