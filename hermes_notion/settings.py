from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from agent.secret_scope import get_secret
from hermes_constants import get_hermes_home

WEBHOOK_PATH = "/webhooks/notion"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8646

# Historical connection metadata, NOT authorization defaults.
AROA_BOT_INTEGRATION_ID = "3f71c0e1-80e8-8148-8d4a-002761fd23b7"
AROA_MENTION_NAMES = ["aroa", "aroa@ufahamu.xyz"]
GRETA_BOT_INTEGRATION_ID = "3f71c0e1-80e8-81bb-8268-002765b23008"
GRETA_BOT_USER_ID = "3f7d872b-594c-8120-9081-000252622a03"
GRETA_MENTION_NAMES = ["greta", "greta@ufahamu.xyz"]


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
    mention_names: List[str] = None
    allowed_user_ids: List[str] = field(default_factory=list)
    allowed_root_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.profile not in {"aroa", "greta"}:
            raise ValueError("unsupported Notion profile")
        if self.mention_names is None:
            self.mention_names = list(AROA_MENTION_NAMES if self.profile == "aroa" else GRETA_MENTION_NAMES)

    @classmethod
    def for_profile(cls, profile: str = "greta") -> NotionSettings:
        if profile not in {"aroa", "greta"}:
            raise ValueError("unsupported Notion profile")
        suffix = profile.upper()
        return cls(
            profile=profile,
            token=get_secret(f"NOTION_API_TOKEN_{suffix}") or get_secret("NOTION_API_TOKEN") or "",
            webhook_secret=get_secret(f"NOTION_WEBHOOK_SECRET_{suffix}") or get_secret("NOTION_WEBHOOK_SECRET") or "",
        )

    @classmethod
    def from_config(cls, extra: Optional[dict] = None) -> NotionSettings:
        extra = extra or {}
        home = get_hermes_home()
        default_profile = home.name if home.parent.name == "profiles" else "aroa"
        if extra.get("profile", default_profile) != default_profile:
            raise ValueError("profile runtime mismatch")
        settings = cls.for_profile(default_profile)
        for name in ("host", "port", "webhook_path", "bot_integration_id", "bot_user_id",
                     "mention_names", "allowed_user_ids", "allowed_root_ids"):
            if name in extra:
                setattr(settings, name, extra[name])
        settings.port = int(settings.port)
        for name in ("mention_names", "allowed_user_ids", "allowed_root_ids"):
            values = getattr(settings, name)
            if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
                raise ValueError(f"invalid {name}")
        return settings
