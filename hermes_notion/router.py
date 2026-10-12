from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .settings import NotionSettings

logger = logging.getLogger(__name__)

@dataclass
class RoutedComment:
    actionable: bool
    reason: str
    comment_id: str
    discussion_id: str
    parent_id: str
    author_id: str
    author_name: str
    text: str
    page_id: Optional[str] = None
    page_title: Optional[str] = None

def evaluate_comment(comment: Dict[str, Any], settings: NotionSettings) -> RoutedComment:
    comment_id = comment.get("id", "")
    discussion_id = comment.get("discussion_id", "")
    parent = comment.get("parent", {})
    parent_id = parent.get("block_id") or parent.get("page_id") or ""
    author = comment.get("created_by", {})
    author_id = author.get("id", "")
    author_name = comment.get("display_name", {}).get("resolved_name") or author.get("name") or "User"

    # 1. Loop guard: ignore comments created by the bot
    if author_id == settings.bot_integration_id:
        return RoutedComment(
            actionable=False,
            reason="authored_by_bot",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=""
        )

    rich_text = comment.get("rich_text", [])
    full_text_parts = []
    
    has_bot_mention = False
    has_other_mention = False

    bot_names = [name.lower() for name in settings.mention_names]

    for item in rich_text:
        itype = item.get("type")
        plain = item.get("plain_text", "")
        full_text_parts.append(plain)

        if itype == "mention":
            mention = item.get("mention", {})
            mtype = mention.get("type")
            if mtype == "user":
                user = mention.get("user", {})
                uid = user.get("id", "")
                uname = (user.get("name") or "").lower()
                uemail = (user.get("person", {}).get("email") or "").lower()
                
                if uid == settings.bot_user_id or any(bn in uname for bn in bot_names) or any(bn in uemail for bn in bot_names):
                    has_bot_mention = True
                else:
                    has_other_mention = True
        elif itype == "text":
            lower_plain = plain.lower()
            if any(f"@{bn}" in lower_plain for bn in bot_names):
                has_bot_mention = True
            elif "@" in lower_plain:
                # Potential other mention in plain text
                words = lower_plain.split()
                for w in words:
                    if w.startswith("@") and not any(bn in w for bn in bot_names):
                        has_other_mention = True

    full_text = "".join(full_text_parts).strip()

    # Deterministic rule evaluation:
    # 1. Addressed to Greta explicitly -> Answer
    if has_bot_mention:
        return RoutedComment(
            actionable=True,
            reason="addressed_to_greta",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=full_text
        )

    # 2. Addressed to someone else (and not Greta) -> Do NOT answer
    if has_other_mention:
        return RoutedComment(
            actionable=False,
            reason="addressed_to_other_user",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=full_text
        )

    # 3. No one addressed -> Answer
    return RoutedComment(
        actionable=True,
        reason="no_user_addressed",
        comment_id=comment_id,
        discussion_id=discussion_id,
        parent_id=parent_id,
        author_id=author_id,
        author_name=author_name,
        text=full_text
    )
