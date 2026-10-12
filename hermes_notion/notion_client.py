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

def _request(token: str, path: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
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
        logger.error("[notion] HTTP %d calling %s %s: %s", err.code, method, path, msg)
        raise NotionClientError(err.code, msg, code) from err
    except Exception as exc:
        logger.error("[notion] Request failed calling %s %s: %s", method, path, exc)
        raise

def get_comment(token: str, comment_id: str) -> Dict[str, Any]:
    return _request(token, f"/comments/{comment_id}", method="GET")

def get_comments_for_block(token: str, block_id: str) -> List[Dict[str, Any]]:
    res = _request(token, f"/comments?block_id={block_id}", method="GET")
    return res.get("results", [])

def get_page(token: str, page_id: str) -> Dict[str, Any]:
    return _request(token, f"/pages/{page_id}", method="GET")

def get_block(token: str, block_id: str) -> Dict[str, Any]:
    return _request(token, f"/blocks/{block_id}", method="GET")

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
