from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from agent.secret_scope import get_secret
from hermes_constants import get_hermes_home, profile_name_for_home


def _scoped_secret(name: str) -> str:
    """Read a credential without raising when no profile secret scope is bound.

    ``agent.secret_scope.get_secret`` raises ``UnscopedSecretError`` on the
    multiplexed gateway when it runs outside a profile scope - which is exactly
    where a platform ``check_fn`` and the default profile's adapter construction
    run. ``gateway.platforms._shared.get_scoped_secret`` is the supported reader
    for those sites: it falls back to this profile's own environment and, with
    ``external_fallback``, to a one-shot build of the profile secret scope, so a
    token that lives in the credentials file is still found at startup.
    """
    try:
        from gateway.platforms._shared import get_scoped_secret
    except Exception:  # pragma: no cover - older core without the helper
        get_scoped_secret = None
    if get_scoped_secret is not None:
        try:
            return get_scoped_secret(name, "", external_fallback=True) or ""
        except Exception:
            return ""
    try:
        return get_secret(name) or ""
    except Exception:
        return ""


WEBHOOK_PATH = "/webhooks/notion"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8646

KOEN_USER_ID = "a28331c7-f20f-48ea-8757-b6d3dd3e22fd"
KOEN_EMAIL = "georges.charles.brain@gmail.com"
GCB_WORKSPACE_ID = "982fd186-4e7c-4435-ad62-bf23735bb30f"

AROA_BOT_INTEGRATION_ID = "3f7d872b-594c-8191-8f90-00377c6844b3"
AROA_BOT_USER_ID = "3f71c0e1-80e8-8148-8d4a-002761fd23b7"
AROA_MENTION_NAMES = ["aroa", "aroa@ufahamu.xyz"]

GRETA_BOT_INTEGRATION_ID = "3f7d872b-594c-810a-8c90-0037ae136e0a"
GRETA_BOT_USER_ID = "3f71c0e1-80e8-81bb-8268-002765b23008"
GRETA_HISTORICAL_PERSON_ID = "3f7d872b-594c-8120-9081-000252622a03"
GRETA_MENTION_NAMES = ["greta", "greta@ufahamu.xyz"]

GRETA_ALLOWED_ROOT_IDS = [
    "3f71c0e1-80e8-8076-be25-f9cadd5041bd",  # house manager database
    "3f71c0e1-80e8-8057-a55f-cea070b2f488",  # family manager pages database
    "3f71c0e1-80e8-8106-9516-fb873d6e5ade",  # Responsibilities of the House Manager
    "3f71c0e1-80e8-81ea-9ae3-db37ead313d8",  # Responsibilities of the Family Manager
]


def valid_profile_name(profile) -> bool:
    return isinstance(profile, str) and profile != "stopped" and bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", profile))


def runtime_profile() -> str:
    # Keep the existing default-profile ownership/session records under their legacy alias.
    name = profile_name_for_home(get_hermes_home()) or "default"
    return "aroa" if name == "default" else name


def legacy_peers() -> list:
    # Public addressing metadata only; never read another profile's config or credentials.
    return [
        {"profile": "aroa", "mention_names": list(AROA_MENTION_NAMES), "bot_user_id": AROA_BOT_USER_ID},
        {"profile": "greta", "mention_names": list(GRETA_MENTION_NAMES), "bot_user_id": GRETA_BOT_USER_ID},
    ]


@dataclass
class NotionSettings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    webhook_path: str = WEBHOOK_PATH
    profile: str = "greta"
    token: str = field(default="", repr=False)
    webhook_secret: str = field(default="", repr=False)
    bot_integration_id: str = ""
    bot_user_id: str = ""
    mention_names: Optional[List[str]] = None
    allowed_user_ids: List[str] = field(default_factory=list)
    allowed_root_ids: List[str] = field(default_factory=list)
    allow_workspace_access: bool = False
    peer_agents: Optional[List[dict]] = None

    def __post_init__(self):
        if not valid_profile_name(self.profile):
            raise ValueError("invalid Notion profile")
        if self.mention_names is None:
            self.mention_names = list(
                AROA_MENTION_NAMES if self.profile == "aroa" else
                GRETA_MENTION_NAMES if self.profile == "greta" else [])
        if self.peer_agents is None:
            self.peer_agents = legacy_peers() if self.profile in {"aroa", "greta"} else []

    @classmethod
    def for_profile(cls, profile: str = "greta", extra: Optional[dict] = None,
                    legacy_defaults: Optional[bool] = None) -> NotionSettings:
        if not valid_profile_name(profile):
            raise ValueError("invalid Notion profile")
        legacy = profile in {"aroa", "greta"} and (legacy_defaults is None or legacy_defaults)
        if not legacy and extra is None:
            raise ValueError("profile configuration required")
        suffix = profile.upper().replace("-", "_")
        settings = cls(
            profile=profile,
            token=_scoped_secret(f"NOTION_API_TOKEN_{suffix}") or _scoped_secret("NOTION_API_TOKEN"),
            webhook_secret=_scoped_secret(f"NOTION_WEBHOOK_SECRET_{suffix}") or _scoped_secret("NOTION_WEBHOOK_SECRET"),
        )
        if legacy:
            # Compatibility only. New profiles inherit none of these identities or grants.
            aroa = profile == "aroa"
            settings.bot_integration_id = AROA_BOT_INTEGRATION_ID if aroa else GRETA_BOT_INTEGRATION_ID
            settings.bot_user_id = AROA_BOT_USER_ID if aroa else GRETA_BOT_USER_ID
            settings.allowed_user_ids = [KOEN_USER_ID]
            settings.allowed_root_ids = ["*"] if aroa else list(GRETA_ALLOWED_ROOT_IDS)
            settings.allow_workspace_access = aroa
        extra = extra or {}
        if not legacy:
            required = ("bot_integration_id", "bot_user_id", "mention_names", "allowed_user_ids", "allowed_root_ids")
            if any(name not in extra or not extra[name] for name in required):
                raise ValueError("explicit profile identity and grants required")
            settings.peer_agents = []
        for name in ("host", "port", "webhook_path", "bot_integration_id", "bot_user_id",
                     "mention_names", "allowed_user_ids", "allowed_root_ids", "allow_workspace_access",
                     "peer_agents"):
            if name not in extra:
                continue
            value = extra[name]
            # Existing installed configs contain empty staged grants. Preserve only legacy behavior.
            if legacy and name in {"allowed_user_ids", "allowed_root_ids", "bot_integration_id", "bot_user_id"} and not value:
                continue
            setattr(settings, name, value)
        settings.port = int(settings.port)
        if not 1 <= settings.port <= 65535:
            raise ValueError("invalid listener port")
        if not isinstance(settings.webhook_path, str) or not re.fullmatch(r"/[a-zA-Z0-9/_-]+", settings.webhook_path):
            raise ValueError("invalid webhook path")
        if type(settings.allow_workspace_access) is not bool:
            raise ValueError("invalid workspace authority")
        for name in ("mention_names", "allowed_user_ids", "allowed_root_ids"):
            values = getattr(settings, name)
            if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
                raise ValueError(f"invalid {name}")
            if not legacy and not values:
                raise ValueError(f"missing {name}")
        for name in ("bot_integration_id", "bot_user_id"):
            if not isinstance(getattr(settings, name), str) or not getattr(settings, name).strip():
                raise ValueError(f"missing {name}")
        if any(root in {"*", "workspace"} for root in settings.allowed_root_ids) and not settings.allow_workspace_access:
            raise ValueError("explicit workspace authority required")
        if not isinstance(settings.peer_agents, list):
            raise ValueError("invalid peer agents")
        for peer in settings.peer_agents:
            if not isinstance(peer, dict) or not valid_profile_name(peer.get("profile")):
                raise ValueError("invalid peer profile")
            names = peer.get("mention_names")
            if not isinstance(names, list) or not names or not all(isinstance(v, str) and v.strip() for v in names):
                raise ValueError("invalid peer mention names")
            if not isinstance(peer.get("bot_user_id", ""), str):
                raise ValueError("invalid peer bot identity")
        return settings

    @classmethod
    def from_config(cls, extra: Optional[dict] = None) -> NotionSettings:
        if extra is None:
            from hermes_cli.config import load_config
            platform = (load_config().get("platforms") or {}).get("notion") or {}
            extra = platform.get("extra", platform)
        if not isinstance(extra, dict):
            raise ValueError("invalid Notion configuration")
        profile = runtime_profile()
        configured = extra.get("profile", profile)
        actual_profile = profile_name_for_home(get_hermes_home()) or "default"
        if configured == "default" and actual_profile == "default":
            configured = "aroa"
        if configured != profile:
            raise ValueError("profile runtime mismatch")
        return cls.for_profile(profile, extra, legacy_defaults=actual_profile in {"default", "greta"})
