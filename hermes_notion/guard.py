"""Allow scoped NTN workspace operations and plugin guidance during Notion turns."""
from gateway.session_context import get_session_env
from hermes_constants import get_hermes_home
from . import storage
from .settings import valid_profile_name

ALLOWED_TOOLS = frozenset({"notion_get_comments", "notion_ntn"})
GUIDANCE_TOOLS = frozenset({"skill_view"})

def _allowed(name, args):
    if not isinstance(name, str) or not isinstance(args, dict):
        return False
    if name in ALLOWED_TOOLS:
        return True
    if name == "skill_view":
        if args.get("name") == "knowledge-management":
            # Runtime profile, not the logical Notion bot name (default is Aroa).
            return (get_session_env("HERMES_SESSION_PROFILE", "") == "default" and
                    get_hermes_home().parent.name != "profiles" and
                    (args.get("file_path") is None or args.get("file_path") == "" or
                     isinstance(args.get("file_path"), str) and args["file_path"] in {
                         "references/workspace.md", "references/wiki-workflows.md",
                         "references/design-basis.md"}))
        if args.get("name") == "notion:notion-page-design":
            # Design guidance is a narrow default-profile addition, not tool access.
            return (get_session_env("HERMES_SESSION_PROFILE", "") == "default" and
                    get_hermes_home().parent.name != "profiles" and
                    (args.get("file_path") is None or args.get("file_path") == "" or
                     isinstance(args.get("file_path"), str) and args["file_path"] in {
                         "references/modern-minimal.md", "references/demonstration.md"}))
        return args.get("name") in {"notion:use", "notion:profile-setup"} and (
            not args.get("file_path") or isinstance(args["file_path"], str) and
            not args["file_path"].startswith("/") and ".." not in args["file_path"].split("/"))
    if name == "tool_describe":
        names = args.get("names")
        names = [names] if isinstance(names, str) else names
        return isinstance(names, list) and bool(names) and all(isinstance(n, str) and n in ALLOWED_TOOLS | GUIDANCE_TOOLS for n in names)
    if name == "tool_call":
        calls = args.get("calls")
        return isinstance(calls, list) and bool(calls) and all(
            isinstance(c, dict) and isinstance(c.get("name"), str) and c.get("name") in ALLOWED_TOOLS | GUIDANCE_TOOLS and
            isinstance(c.get("arguments"), dict) and _allowed(c["name"], c["arguments"]) for c in calls)
    return False

def check(tool_name="", args=None, **_):
    if get_session_env("HERMES_SESSION_PLATFORM", "") != "notion":
        return None
    if not _allowed(tool_name, args or {}):
        return {"action": "block", "message": "Use notion_ntn for Notion workspace operations, notion_get_comments for discussion reads, or skill_view(name='notion:use') for instructions. Return your final answer for gateway delivery. Shell, credentials, MCP, delegation and duplicate direct replies are not allowed."}
    discussion = get_session_env("HERMES_SESSION_THREAD_ID", "")
    profile = get_session_env("HERMES_SESSION_PROFILE", "")
    if profile == "default" and get_hermes_home().parent.name != "profiles":
        profile = "aroa"
    chat_id = get_session_env("HERMES_SESSION_CHAT_ID", "")
    owned = storage.comment_has_owned_discussion(get_session_env("HERMES_SESSION_MESSAGE_ID", ""), chat_id[len("notion:page:"):], profile) if chat_id.startswith("notion:page:") else (
        bool(discussion) and storage.get_discussion_owner(discussion) == profile)
    if not valid_profile_name(profile) or not owned:
        return {"action": "block", "message": "This Notion discussion is stopped or is not owned by this profile."}
    return None
