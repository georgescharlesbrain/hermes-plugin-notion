from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from .settings import NotionSettings

logger = logging.getLogger(__name__)

KOEN_USER_ID = "a28331c7-f20f-48ea-8757-b6d3dd3e22fd"
KOEN_EMAIL = "georges.charles.brain@gmail.com"

AROA_BOT_ID = "3f71c0e1-80e8-8148-8d4a-002761fd23b7"
GRETA_BOT_ID = "3f71c0e1-80e8-81bb-8268-002765b23008"

# Historical IDs above support compatibility/tests only; no implicit caller grants.

TERMINAL_ACKNOWLEDGMENT_PATTERNS: Set[str] = {
    "thank you", "thanks", "thx", "ty", "thank you very much", "thank you so much",
    "ok", "okay", "got it", "noted", "k", "cool", "great", "perfect", "done",
    "all good", "understood", "no problem", "youre welcome", "you are welcome",
    "great thanks", "thanks a lot", "many thanks", "perfect thank you"
}

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

def is_author_authorized(comment: Dict[str, Any], target_bot: str,
                         allowed_user_ids: Optional[List[str]] = None) -> bool:
    """Only configured immutable human IDs grant authority; names/emails/bots do not."""
    author = comment.get("created_by", {})
    if author.get("type") == "bot" or comment.get("display_name", {}).get("type") == "integration":
        return False
    return bool(author.get("id") and author.get("id") in (allowed_user_ids or []))

def is_terminal_acknowledgment(text: str, mention_names: Optional[List[str]] = None) -> bool:
    """True when text is solely an acknowledgment or gratitude with no instruction/question."""
    if not text:
        return False
    if "?" in text:
        return False
    lower = text.lower()
    # Strip known bot names / mentions
    if mention_names:
        for name in mention_names:
            lower = re.sub(rf"@?{re.escape(name.lower())}\b", "", lower)
    # Remove punctuation
    cleaned = re.sub(r"[^\w\s]", "", lower).strip()
    if not cleaned:
        return False
    if cleaned in TERMINAL_ACKNOWLEDGMENT_PATTERNS:
        return True
    return False

def _is_addressed_at_start(plain_text: str, rich_text: List[Dict[str, Any]], names: List[str], bot_user_id: str) -> bool:
    """True when the bot is addressed at the very beginning of the comment."""
    clean_text = plain_text.strip()
    lower_text = clean_text.lower()
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
                if bool(bot_user_id and uid == bot_user_id):
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
                is_our_bot = bool(bot_user_id and uid == bot_user_id)
                if not is_our_bot:
                    return True

    if clean_text.startswith("@"):
        first_word = clean_text.split()[0].lstrip("@").rstrip(":,!").lower()
        if not any(bn == first_word for bn in bot_names):
            return True

    return False

def evaluate_comment(
    comment: Dict[str, Any],
    settings: NotionSettings,
    discussion_owner: Optional[str] = None
) -> RoutedComment:
    comment_id = comment.get("id", "")
    discussion_id = comment.get("discussion_id", "")
    parent = comment.get("parent", {})
    parent_id = parent.get("block_id") or parent.get("page_id") or ""
    author = comment.get("created_by", {})
    author_id = author.get("id", "")
    author_name = comment.get("display_name", {}).get("resolved_name") or author.get("name") or "User"

    rich_text = comment.get("rich_text", [])
    full_text_parts = [item.get("plain_text", "") for item in rich_text]
    full_text = "".join(full_text_parts).strip()

    if not comment_id or not discussion_id or not author_id or not full_text:
        return RoutedComment(False, "invalid_comment", comment_id, discussion_id,
                             parent_id, author_id, author_name, full_text)

    # 1. Loop guard: A bot NEVER answers a comment created by ITSELF
    if author_id and author_id in {settings.bot_integration_id, settings.bot_user_id}:
        return RoutedComment(
            actionable=False,
            reason="authored_by_target_bot",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=""
        )

    # 2. Authorization check: Is this author allowed to address this bot?
    if not is_author_authorized(comment, settings.profile, settings.allowed_user_ids):
        return RoutedComment(
            actionable=False,
            reason="author_not_authorized",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=full_text
        )

    stop_text = full_text.lower()
    for name in sorted(settings.mention_names, key=len, reverse=True):
        stop_text = re.sub(rf"^@?{re.escape(name.lower())}([:\s,!-]+|$)", "", stop_text)
    if len(full_text) > 8192:
        return RoutedComment(False, "request_budget_exceeded", comment_id, discussion_id,
                             parent_id, author_id, author_name, "")
    if re.match(r"^(fyi|status|update)\s*:", stop_text):
        return RoutedComment(False, "non_actionable_update", comment_id, discussion_id,
                             parent_id, author_id, author_name, full_text)
    if stop_text.strip(" .!") in {"stop", "cancel", "pause"}:
        return RoutedComment(False, "stop_requested", comment_id, discussion_id,
                             parent_id, author_id, author_name, full_text)

    # 3. Terminal acknowledgment guard: Gratitude / Acknowledgment without request closes turn
    if is_terminal_acknowledgment(full_text, settings.mention_names):
        return RoutedComment(
            actionable=False,
            reason="terminal_acknowledgment",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=full_text
        )

    # 4. Check if another user/bot is addressed at start
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

    # 5. Check if target bot is addressed at start
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

    # 6. Check if target bot is mentioned in middle (topic only, not addressed)
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

    # 7. Check thread continuation: if this bot owns this discussion, keep answering
    if discussion_owner and discussion_owner.lower() == settings.profile.lower():
        return RoutedComment(
            actionable=True,
            reason="thread_continuation",
            comment_id=comment_id,
            discussion_id=discussion_id,
            parent_id=parent_id,
            author_id=author_id,
            author_name=author_name,
            text=full_text
        )

    # 8. No user/bot addressed and not an existing thread for this bot
    return RoutedComment(
        actionable=False,
        reason="not_addressed",
        comment_id=comment_id,
        discussion_id=discussion_id,
        parent_id=parent_id,
        author_id=author_id,
        author_name=author_name,
        text=full_text
    )
