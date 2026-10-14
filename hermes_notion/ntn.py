"""NTN workspace execution without a shell or cross-profile credential access."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from gateway.session_context import get_session_env
from hermes_constants import get_hermes_home
from . import notion_client, policy, storage
from .settings import NotionSettings, legacy_peers

MAX_OUTPUT = 60000
MAX_INPUT = 262144
ID = r"[0-9a-fA-F-]{32,36}"

def environment(home: Path, token: str) -> dict:
    # No ambient provider, peer-profile, shell-editor or worker credentials.
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR") if k in os.environ}
    state = home / "plugin-data" / "notion" / "cli"
    env.update({"HERMES_HOME": str(home),
                "NOTION_API_TOKEN": token, "NOTION_API_BASE_URL": "https://api.notion.com",
                "NOTION_API_DOCS_BASE_URL": "https://developers.notion.com",
                "NOTION_BASE_URL": "https://www.notion.com", "NOTION_ENV": "prod",
                "NOTION_HOME": str(state), "NOTION_KEYRING": "0",
                "XDG_CONFIG_HOME": str(state / "config"), "XDG_CACHE_HOME": str(state / "cache")})
    state.mkdir(parents=True, exist_ok=True)
    return env

def _scope(settings, target):
    if not policy.is_strict_notion_id(target):
        return False
    return policy.in_scope(settings.token, target, settings.allowed_root_ids, profile=settings.profile)

def _current_request(settings):
    if get_session_env("HERMES_SESSION_PLATFORM", "") != "notion":
        return None
    cid = get_session_env("HERMES_SESSION_MESSAGE_ID", "")
    page = get_session_env("HERMES_SESSION_CHAT_ID", "").removeprefix("notion:page:")
    if not storage.comment_has_owned_discussion(cid, page, settings.profile):
        raise ValueError("discussion_not_owned")
    original = notion_client.get_comment(settings.token, cid)
    author = (original.get("created_by") or {}).get("id")
    parent = original.get("parent") or {}
    target = parent.get("block_id") or parent.get("page_id")
    if original.get("discussion_id") != storage.get_comment_discussion(cid):
        raise ValueError("request_discussion_mismatch")
    gate = policy.check_mutation_gate(settings.profile, settings.token, target, "update",
        settings.allowed_root_ids, settings.allowed_user_ids, author,
        allow_workspace_access=settings.allow_workspace_access)
    if not gate.allowed:
        raise ValueError(gate.reason)
    return original

def _api(argv, body):
    endpoint = argv[1] if len(argv) > 1 else ""
    if endpoint in {"ls", "help", "--help", "-h"}:
        if body is not None or any(a not in {"--help", "-h"} for a in argv[2:]):
            raise ValueError("unsupported_listing_options")
        return False, [], False
    is_docs = any(a in {"--spec", "--docs", "--help", "-h"} for a in argv[2:])
    pattern = r"/?v1/[A-Za-z0-9_/{}/-]+" if is_docs else r"/?v1/[A-Za-z0-9_/-]+"
    if not re.fullmatch(pattern, endpoint) or ".." in endpoint:
        raise ValueError("relative_api_path_required")
    path = endpoint.lstrip("/").split("/")
    if len(path) < 2 or path[1] not in {"pages", "blocks", "databases", "data_sources", "comments", "file_uploads", "search", "users", "views", "custom_emojis", "async_tasks"}:
        raise ValueError("workspace_endpoint_required")
    method = "POST" if body is not None else "GET"
    data = body
    targets = []
    docs = False
    seen_options = set()
    i = 2
    while i < len(argv):
        arg = argv[i]
        if arg in {"-X", "--method", "--notion-version", "-d", "--data"}:
            if i + 1 >= len(argv): raise ValueError("missing_option_value")
            value = argv[i + 1]
            canonical = "method" if arg in {"-X", "--method"} else "data" if arg in {"-d", "--data"} else "version"
            if canonical in seen_options: raise ValueError("duplicate_option")
            seen_options.add(canonical)
            if arg in {"-X", "--method"}: method = value.upper()
            elif arg in {"-d", "--data"}:
                if body is not None or value.startswith("@"): raise ValueError("json_body_only")
                data = json.loads(value)
                if method == "GET": method = "POST"
            i += 2
            continue
        if arg in {"--docs", "--spec", "-h", "--help"}:
            docs = True
        elif "==" in arg:
            key, value = arg.split("==", 1)
            if key in {"block_id", "page_id", "database_id", "data_source_id"}:
                targets.append(value)
        elif arg.startswith("Accept:") or arg.startswith("Notion-Version:"):
            pass
        else:
            raise ValueError("use_json_body_for_api_writes")
        i += 1
    if method not in {"GET", "POST", "PATCH", "DELETE"}:
        raise ValueError("unsupported_method")
    if docs:
        return False, [], False
    if len(path) > 2 and path[1] in {"users", "file_uploads"}:
        pass
    elif len(path) > 2 and policy.is_strict_notion_id(path[2]):
        targets.append(path[2])
    elif len(path) > 2 and path[1] not in {"users"}:
        raise ValueError("invalid_api_target")
    if path[1] == "comments" and len(path) > 2:
        # Comment IDs are not page/block ancestry IDs. Resolve before scope validation.
        targets[-1:] = [("comment", path[2])]
    if data is not None:
        if not isinstance(data, dict): raise ValueError("object_body_required")
        parent = data.get("parent") or {}
        if isinstance(parent, dict):
            for key in ("page_id", "block_id", "database_id", "data_source_id"):
                if parent.get(key): targets.append(parent[key])
        for key in ("page_id", "block_id", "database_id", "data_source_id"):
            if data.get(key): targets.append(data[key])
        if data.get("discussion_id"):
            targets.append(("discussion", data["discussion_id"]))
    read_post = method == "POST" and (path[1] == "search" or path[-1] == "query")
    mutation = method != "GET" and not read_post
    # Creation must have an explicit approved parent; no workspace-root default.
    if mutation and path[1] in {"pages", "databases", "data_sources", "blocks", "comments"} and not targets:
        raise ValueError("approved_target_or_parent_required")
    if mutation and not targets and path[1] != "file_uploads":
        raise ValueError("approved_target_or_parent_required")
    destructive = method == "DELETE" or bool(data and (data.get("archived") or data.get("in_trash") or data.get("allow_deleting_content")))
    return mutation, targets, destructive

def validate(argv, body=None, stdin=None):
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or "\x00" in a for a in argv):
        raise ValueError("args_must_be_strings")
    if len(argv) > 128 or len(json.dumps([argv, body, stdin])) > MAX_INPUT:
        raise ValueError("input_budget_exceeded")
    if argv[0] not in {"api", "pages", "datasources", "files", "whoami", "--help", "--version", "-h", "-V"}:
        raise ValueError("workspace_commands_only")
    if any(a.startswith(("--workers-config-file", "--allow-deleting-content", "--filter-file", "--env")) or a == "--file" or a.startswith("--file=") or a.lower().startswith(("authorization:", "host:")) for a in argv):
        raise ValueError("credential_or_file_override_forbidden")
    if argv[0] == "api":
        if stdin is not None: raise ValueError("use_body_for_api_input")
        return _api(argv, body)
    if body is not None: raise ValueError("body_requires_api")
    if argv[0] in {"whoami", "--help", "--version", "-h", "-V"}:
        if len(argv) != 1: raise ValueError("unsupported_options")
        return False, [], False
    if len(argv) < 2 or argv[1] in {"help", "--help", "-h"}:
        return False, [], False
    verb = argv[1]
    takes_value = {
        "pages": {"--content", "--parent", "--notion-version"},
        "datasources": {"--limit", "--start-cursor", "--filter", "--sort", "--sorts", "--notion-version"},
        "files": {"--external-url", "--filename", "--content-type", "--notion-version"},
    }[argv[0]]
    flags = {"--json", "--plain", "-h", "--help"}
    start = 2 if verb in {"create", "list", "ls"} else 3
    seen = set()
    i = start
    while i < len(argv):
        option = argv[i]
        if option in seen: raise ValueError("duplicate_option")
        seen.add(option)
        if option in takes_value:
            if i + 1 >= len(argv): raise ValueError("missing_option_value")
            i += 2
        elif option in flags:
            i += 1
        else: raise ValueError("unsupported_or_file_option")
    if argv[0] == "pages":
        if verb == "create":
            if "--parent" not in argv: raise ValueError("explicit_parent_required")
            raw = argv[argv.index("--parent") + 1]
            if not re.fullmatch(r"(page|database|data-source):" + ID, raw):
                raise ValueError("invalid_parent")
            targets = [raw.split(":", 1)[1]]
        elif verb in {"get", "edit", "trash"} and len(argv) > 2:
            targets = [argv[2]]
        else: raise ValueError("unsupported_page_command")
        if verb in {"edit", "create"} and "--content" not in argv and stdin is None:
            raise ValueError("content_required_no_editor")
        return verb != "get", targets, verb == "trash"
    if argv[0] == "datasources":
        if verb not in {"query", "resolve"} or len(argv) < 3: raise ValueError("unsupported_datasource_command")
        return False, [argv[2]], False
    if argv[0] == "files":
        if verb not in {"create", "get", "list", "ls"}: raise ValueError("unsupported_file_command")
        if verb == "create" and "--external-url" not in argv and stdin is None:
            raise ValueError("upload_input_required")
        return verb == "create", [], False
    raise ValueError("unsupported_command")

def _approved_delete(original, targets, mention_names=None):
    text = "".join(r.get("plain_text", "") for r in (original or {}).get("rich_text", []))
    directives = []
    names = mention_names if mention_names is not None else [name for peer in legacy_peers() for name in peer["mention_names"]]
    prefix = "@?(?:" + "|".join(re.escape(name) for name in names) + r")[,:]?\s+" if names else ""
    pattern = "(?:" + prefix + ")?" if prefix else ""
    for line in text.strip().splitlines():
        match = re.fullmatch(pattern + r"approve-delete\s+(" + ID + r")", line.strip(), re.IGNORECASE)
        if not match:
            return False
        directives.append(policy.normalize_identifier(match[1]))
    return bool(targets) and all(policy.normalize_identifier(t) in directives for t in targets)


def execute(args: dict, settings=None) -> dict:
    settings = settings or NotionSettings.from_config()
    if not settings.token: return {"ok": False, "error": "notion_not_configured"}
    try:
        argv = args.get("args")
        body, stdin = args.get("body"), args.get("stdin")
        if stdin is not None and not isinstance(stdin, str): raise ValueError("stdin_must_be_text")
        mutation, targets, destructive = validate(argv, body, stdin)
        original = _current_request(settings)
        if original and mutation and argv[0] == "api" and argv[1].lstrip("/").split("/")[1] == "comments":
            raise ValueError("comment_mutations_use_gateway")
        checked = []
        for target in targets:
            if isinstance(target, tuple):
                kind, ident = target
                if kind == "comment":
                    obj = notion_client.get_comment(settings.token, ident)
                    parent = obj.get("parent") or {}
                    target = parent.get("block_id") or parent.get("page_id")
                else:
                    target = storage.get_discussion_parent(ident)
            if not _scope(settings, target): raise ValueError("outside_allowed_roots")
            checked.append(target)
        if destructive:
            if not original or not _approved_delete(original, checked, settings.mention_names):
                raise ValueError("explicit_delete_approval_required")
        executable = shutil.which("ntn")
        if not executable: raise ValueError("ntn_not_installed")
        command = [executable, *argv]
        if body is not None: command.extend(["--data", json.dumps(body)])
        # No shell expansion, file input or interactive editor.
        cid = (original or {}).get("id") or get_session_env("HERMES_SESSION_MESSAGE_ID", "")
        digest = hashlib.sha256(json.dumps([cid, argv, body, stdin], sort_keys=True).encode()).hexdigest()
        if mutation:
            previous = storage.claim_ntn_operation(digest, cid or None)
            if previous is not None:
                return json.loads(previous) if previous else {"ok": False, "error": "mutation_result_unverified_no_retry"}
        if original:
            _current_request(settings)  # Recheck stop, ownership and human authorization immediately before execution.
        env = environment(Path(get_hermes_home()), settings.token)
        result = subprocess.run(command, input=stdin or "", text=True, capture_output=True,
                                timeout=120, check=False, env=env, cwd=env["NOTION_HOME"])
        output = (result.stdout or "").replace(settings.token, "[REDACTED]")
        errors = (result.stderr or "").replace(settings.token, "[REDACTED]")
        response = {"ok": result.returncode == 0, "exit_code": result.returncode,
                    "stdout": output[:MAX_OUTPUT], "stderr": errors[:4000],
                    "truncated": len(output) > MAX_OUTPUT,
                    "write_requires_readback": mutation}
        if mutation and result.returncode == 0:
            storage.finish_ntn_operation(digest, json.dumps(response))
        return response
    except ValueError as exc:
        # Only our fixed validation messages, never CLI exception arguments.
        known = str(exc)
        return {"ok": False, "error": known if re.fullmatch(r"[a-z_]+", known) else "invalid_request"}
    except Exception:
        return {"ok": False, "error": "ntn_failed_or_timed_out_no_automatic_retry"}
