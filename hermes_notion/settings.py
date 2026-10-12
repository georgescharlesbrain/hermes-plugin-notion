from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Optional

WEBHOOK_PATH = "/webhooks/notion"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8646
DEFAULT_PROFILE = "greta"

DEFAULT_BOT_INTEGRATION_ID = "3f71c0e1-80e8-81bb-8268-002765b23008"
DEFAULT_BOT_USER_ID = "3f7d872b-594c-8120-9081-000252622a03"
DEFAULT_MENTION_NAMES = ["greta", "greta@ufahamu.xyz"]

@dataclass
class NotionSettings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    webhook_path: str = WEBHOOK_PATH
    profile: str = DEFAULT_PROFILE
    token: str = ""
    webhook_secret: str = ""
    bot_integration_id: str = DEFAULT_BOT_INTEGRATION_ID
    bot_user_id: str = DEFAULT_BOT_USER_ID
    mention_names: List[str] = None

    def __post_init__(self):
        if self.mention_names is None:
            self.mention_names = list(DEFAULT_MENTION_NAMES)

    @classmethod
    def from_config(cls, extra: Optional[dict] = None) -> NotionSettings:
        extra = extra or {}
        token = extra.get("token") or os.getenv("NOTION_API_TOKEN", "") or os.getenv("NOTION_API_KEY", "")
        secret = extra.get("webhook_secret") or os.getenv("NOTION_WEBHOOK_SECRET", "")
        profile = extra.get("profile") or os.getenv("HERMES_PROFILE") or DEFAULT_PROFILE
        host = extra.get("host") or DEFAULT_HOST
        port = int(extra.get("port") or DEFAULT_PORT)
        bot_integration_id = extra.get("bot_integration_id") or os.getenv("NOTION_BOT_INTEGRATION_ID") or DEFAULT_BOT_INTEGRATION_ID
        bot_user_id = extra.get("bot_user_id") or os.getenv("NOTION_BOT_USER_ID") or DEFAULT_BOT_USER_ID
        mentions_env = os.getenv("NOTION_MENTION_NAMES")
        mentions = [m.strip() for m in mentions_env.split(",")] if mentions_env else list(DEFAULT_MENTION_NAMES)

        return cls(
            host=host,
            port=port,
            webhook_path=extra.get("webhook_path") or WEBHOOK_PATH,
            profile=profile,
            token=token,
            webhook_secret=secret,
            bot_integration_id=bot_integration_id,
            bot_user_id=bot_user_id,
            mention_names=mentions
        )
