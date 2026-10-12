from __future__ import annotations

import logging
import re
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

def _is_addressed_at_start(plain_text: str, rich_text: List[Dict[str, Any]], names: List[str], bot_user_id: str) -> bool:
    """True when the bot is addressed at the very beginning of the comment."""
    clean_text = plain_text.strip()
    lower_text = clean_text.lower()
    bot_names = [n.lower() for n in names]

    # Check first rich_text item if it is a mention
    if rich_text:
        first_item = rich_text[0]
        if first_item.get("type") == "mention":
            mention = first_item.get("mention", {})
            if mention.get("type") == "user":
                user = mention.get("user", {})
                uid = user.get("id", "")
                uname = (user.get("name") or "").lower()
                uemail = (user.get("person", {}).get("email") or "").lower()
                if (bot_user_id and uid == bot_user_id) or any(bn in uname for bn in bot_names) or any(bn in uemail for bn in bot_names):
                    return True

    for bn in bot_names:
        pattern = rf"^(@?{re.escape(bn)})([:\s,!-].*|$)"
        if re.match(pattern, lower_text):
            return True

    return False

def _other_addressed_at_start(plain_text: str, rich_text: List[Dict[str, Any]], names: List[str], bot_user_id: str) -> bool:
    """True when another user/bot is explicitly addressed at the start."""
    clean_text = plain_text.strip()
    bot_names = [n.lower() for n in names]

    if rich_text:
        first_item = rich_text[0]
        if first_item.get("type") == "mention":
            mention = first_item.get("mention", {})
            if mention.get("type") == "user":
                user = mention.get("user", {})
                uid = user.get("id", "")
                uname = (user.get("name") or "").lower()
                uemail = (user.get("person", {}).get("email") or "").lower()
                is_our_bot = (bot_user_id and uid == bot_user_id) or any(bn in uname for bn in bot_names) or any(bn in uemail for bn in bot_names)
                if not is_our_bot:
                    return True

    if clean_text.startswith("@"):
        first_word = clean_text.split()[0].lstrip("@").rstrip(":,!").lower()
        if not any(bn == first_word for bn in bot_names):
            return True

    return False

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
    full_text_parts = [item.get("plain_text", "") for item in rich_text]
    full_text = "".join(full_text_parts).strip()

    # 2. Check if another user is addressed at start
    if _other_addressed_at_start(full_text, rich_text, settings.mention_names, settings.bot_user_id):
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

    # 3. Check if bot is addressed at start
    if _is_addressed_at_start(full_text, rich_text, settings.mention_names, settings.bot_user_id):
        return RoutedComment(
            actionable=True,
            reason="addressed_at_start",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=full_text
        )

    # 4. Check if bot is mentioned somewhere in the middle (topic only, not addressed)
    bot_names = [n.lower() for n in settings.mention_names]
    lower_full = full_text.lower()
    has_mention_in_middle = any(f"@{bn}" in lower_full for bn in bot_names) or any(f" {bn} " in f" {lower_full} " for bn in bot_names)
    if has_mention_in_middle:
        return RoutedComment(
            actionable=False,
            reason="mentioned_as_topic_not_addressed",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=full_text
        )

    # 5. No user addressed -> default answering
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
