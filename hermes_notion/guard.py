"""Permit only profile-scoped comment reads during automated Notion turns."""
from gateway.session_context import get_session_env
from . import storage

ALLOWED_TOOLS = frozenset({"notion_get_comments"})


def check(tool_name="", args=None, **_):
    if get_session_env("HERMES_SESSION_PLATFORM", "") != "notion":
        return None
    if tool_name not in ALLOWED_TOOLS:
        return {"action": "block", "message": "Notion turns can only read permitted comments. Return your answer for gateway delivery."}
    discussion = get_session_env("HERMES_SESSION_THREAD_ID", "")
    profile = get_session_env("HERMES_SESSION_PROFILE", "")
    if profile not in {"aroa", "greta"} or not discussion or storage.get_discussion_owner(discussion) != profile:
        return {"action": "block", "message": "This Notion discussion is stopped or is not owned by this profile."}
    return None
