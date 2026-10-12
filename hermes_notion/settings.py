from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Optional

WEBHOOK_PATH = "/webhooks/notion"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8646

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
    token: str = ""
    webhook_secret: str = ""
    bot_integration_id: str = GRETA_BOT_INTEGRATION_ID
    bot_user_id: str = GRETA_BOT_USER_ID
    mention_names: List[str] = None

    def __post_init__(self):
        if self.mention_names is None:
            self.mention_names = list(GRETA_MENTION_NAMES)

    @classmethod
    def for_profile(cls, profile: str = "greta") -> NotionSettings:
        profile = profile.lower()
        if profile == "aroa":
            token = os.getenv("NOTION_API_TOKEN_AROA") or os.getenv("NOTION_API_TOKEN", "")
            bot_integration_id = os.getenv("NOTION_BOT_INTEGRATION_ID_AROA") or AROA_BOT_INTEGRATION_ID
            bot_user_id = os.getenv("NOTION_BOT_USER_ID_AROA", "")
            mentions = [m.strip() for m in os.getenv("NOTION_MENTION_NAMES_AROA", "").split(",") if m.strip()] or list(AROA_MENTION_NAMES)
        else:
            token = os.getenv("NOTION_API_TOKEN_GRETA") or os.getenv("NOTION_API_TOKEN", "")
            bot_integration_id = os.getenv("NOTION_BOT_INTEGRATION_ID_GRETA") or GRETA_BOT_INTEGRATION_ID
            bot_user_id = os.getenv("NOTION_BOT_USER_ID_GRETA") or GRETA_BOT_USER_ID
            mentions = [m.strip() for m in os.getenv("NOTION_MENTION_NAMES_GRETA", "").split(",") if m.strip()] or list(GRETA_MENTION_NAMES)

        return cls(
            profile=profile,
            token=token,
            bot_integration_id=bot_integration_id,
            bot_user_id=bot_user_id,
            mention_names=mentions
        )

    @classmethod
    def from_config(cls, extra: Optional[dict] = None) -> NotionSettings:
        extra = extra or {}
        profile = extra.get("profile") or os.getenv("HERMES_PROFILE") or "greta"
        settings = cls.for_profile(profile)
        if extra.get("token"):
            settings.token = extra["token"]
        if extra.get("webhook_secret"):
            settings.webhook_secret = extra["webhook_secret"]
        if extra.get("host"):
            settings.host = extra["host"]
        if extra.get("port"):
            settings.port = int(extra["port"])
        if extra.get("bot_integration_id"):
            settings.bot_integration_id = extra["bot_integration_id"]
        return settings
