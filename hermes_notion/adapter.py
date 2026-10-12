"""The notion gateway platform: Notion webhooks in, one agent session per discussion thread."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.platforms.event import MessageEvent, MessageType

from . import notion_client
from . import router
from . import storage
from .settings import NotionSettings, WEBHOOK_PATH

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    web = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)

PLATFORM_NAME = "notion"
MAX_BODY_BYTES = 1_048_576

plugin_context: Any = None

def check_requirements() -> bool:
    """Available when NOTION_API_TOKEN is set."""
    token = os.getenv("NOTION_API_TOKEN") or os.getenv("NOTION_API_KEY")
    return bool(token and token.strip())

def is_connected(adapter: Optional[BasePlatformAdapter] = None) -> bool:
    return bool(adapter and getattr(adapter, "_running", False))

def _profile_from_path(path: str) -> str:
    path_lower = path.lower()
    if "aroa" in path_lower:
        return "aroa"
    return "greta"

class NotionAdapter(BasePlatformAdapter):
    """Notion <-> Hermes: HMAC-verified comment webhooks, thread write-back."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform(PLATFORM_NAME))
        self.settings = NotionSettings.from_config(getattr(config, "extra", None))
        self._http_runner = None
        self._background: Set[asyncio.Task] = set()
        self._running = False
        self._owner_profile = self.settings.profile

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not check_requirements():
            logger.warning("[notion] NOTION_API_TOKEN is not configured; adapter will not start.")
            return False

        if not AIOHTTP_AVAILABLE or web is None:
            logger.error("[notion] aiohttp is not installed; cannot start webhook server.")
            return False

        self.settings = NotionSettings.from_config(getattr(self.config, "extra", None))

        app = web.Application(client_max_size=MAX_BODY_BYTES)
        # Support base and profile-specific paths
        app.router.add_post(self.settings.webhook_path, self._handle_webhook)
        app.router.add_get(self.settings.webhook_path, self._handle_health)
        app.router.add_post("/webhooks/notion/greta", self._handle_webhook)
        app.router.add_get("/webhooks/notion/greta", self._handle_health)
        app.router.add_post("/webhooks/notion/aroa", self._handle_webhook)
        app.router.add_get("/webhooks/notion/aroa", self._handle_health)

        from gateway.platforms.shared_ingress import bind_listener

        self._http_runner = await bind_listener(
            self, app, self.settings.host, self.settings.port, self.settings.webhook_path
        )
        self._running = True
        logger.info(
            "[notion] Listening on %s:%d%s (multi-profile) for profile %s",
            self.settings.host,
            self.settings.port,
            self.settings.webhook_path,
            self.settings.profile,
        )
        return True

    async def disconnect(self) -> None:
        for task in list(self._background):
            task.cancel()
        if self._http_runner is not None:
            await self._http_runner.cleanup()
            self._http_runner = None
        self._running = False
        logger.info("[notion] Disconnected")

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"name": chat_id, "type": "channel"}

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send agent response back to Notion comment thread."""
        meta = metadata or {}
        discussion_id = meta.get("discussion_id")
        if not discussion_id and chat_id.startswith("notion:thread:"):
            discussion_id = chat_id[len("notion:thread:"):]

        if not discussion_id:
            logger.warning("[notion] Cannot send comment reply: missing discussion_id in chat_id %s", chat_id)
            return SendResult(success=False, error="missing discussion_id")

        token = self.settings.token
        if not token:
            logger.error("[notion] Cannot post reply: missing NOTION_API_TOKEN")
            return SendResult(success=False, error="missing NOTION_API_TOKEN")

        try:
            logger.info("[notion] Posting reply to discussion %s (%d chars)", discussion_id, len(content))
            res = await asyncio.to_thread(
                notion_client.create_comment_reply,
                token=token,
                discussion_id=discussion_id,
                content=content,
            )
            comment_id = res.get("id")
            return SendResult(success=True, message_id=comment_id)
        except Exception as exc:
            logger.exception("[notion] Failed to create comment reply in discussion %s: %s", discussion_id, exc)
            return SendResult(success=False, error=str(exc))

    async def _handle_health(self, request: web.Request) -> web.Response:
        profile = _profile_from_path(request.path)
        return web.Response(text=f"Notion Webhook Listener is Active for [{profile}]\n", status=200)

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        if request.content_length is not None and request.content_length > MAX_BODY_BYTES:
            return web.json_response({"error": "payload too large"}, status=413)

        raw_body = await request.read()
        profile = _profile_from_path(request.path)

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            payload = {}

        # 1. Verification handshake handling
        if "verification_token" in payload:
            v_token = payload["verification_token"]
            logger.info("[notion] Received verification handshake for %s with token: %s", profile, v_token)
            await asyncio.to_thread(storage.save_verification_token, v_token, profile, request.path)
            return web.json_response({"status": "received", "verification_token": v_token}, status=200)

        # 2. Signature verification
        secret = await asyncio.to_thread(storage.get_verification_token, profile) or self.settings.webhook_secret
        signature_header = request.headers.get("X-Notion-Signature") or request.headers.get("x-notion-signature")

        if secret and signature_header:
            if signature_header.startswith("sha256="):
                signature_header = signature_header[len("sha256="):]
            computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature_header, computed):
                logger.warning("[notion] Invalid X-Notion-Signature received for profile %s", profile)
                return web.json_response({"error": "invalid signature"}, status=401)
        elif secret and not signature_header:
            logger.warning("[notion] Missing X-Notion-Signature header on webhook request for profile %s", profile)
            return web.json_response({"error": "missing signature"}, status=401)

        # 3. Process actionable events
        events: List[Dict[str, Any]] = []
        if isinstance(payload, list):
            events = payload
        elif "events" in payload and isinstance(payload["events"], list):
            events = payload["events"]
        elif isinstance(payload, dict) and payload:
            events = [payload]

        for ev in events:
            ev_type = ev.get("type", "")
            entity = ev.get("entity", {})
            entity_type = entity.get("type", "")
            entity_id = entity.get("id", "") or ev.get("id", "")

            if ev_type.startswith("comment") or entity_type == "comment":
                comment_id = entity_id
                if comment_id:
                    self._spawn(self._process_comment_id(comment_id, profile))

        return web.json_response({"status": "accepted"}, status=200)

    async def _process_comment_id(self, comment_id: str, profile: str) -> None:
        token = self.settings.token
        if not token:
            logger.error("[notion] Cannot fetch comment %s: missing NOTION_API_TOKEN", comment_id)
            return

        try:
            comment_obj = await asyncio.to_thread(notion_client.get_comment, token, comment_id)
        except Exception as exc:
            logger.warning("[notion] Failed to fetch comment %s from Notion API: %s", comment_id, exc)
            return

        routed = router.evaluate_comment(comment_obj, self.settings)
        if not routed.actionable:
            logger.info("[notion] Comment %s ignored (reason: %s)", comment_id, routed.reason)
            return

        logger.info("[notion] Actionable comment %s from %s: %s", comment_id, routed.author_name, routed.reason)

        chat_id = f"notion:thread:{routed.discussion_id}"
        source = self.build_source(
            chat_id=chat_id,
            chat_name=f"Notion Thread {routed.discussion_id[:8]}",
            chat_type="channel",
            user_id=routed.author_id,
            user_name=routed.author_name,
            thread_id=routed.discussion_id,
            role_authorized=True,
        )
        source.profile = profile

        text_prompt = (
            f"Notion comment from {routed.author_name}:\n\n"
            f"{routed.text}\n\n"
            f"[Discussion ID: {routed.discussion_id} | Comment ID: {routed.comment_id}]"
        )

        msg_event = MessageEvent(
            text=text_prompt,
            message_type=MessageType.TEXT,
            source=source,
            internal=True,
            allow_gateway_control=False,
            message_id=routed.comment_id,
            metadata={
                "discussion_id": routed.discussion_id,
                "comment_id": routed.comment_id,
                "notion_profile": profile,
            },
        )
        await self.handle_message(msg_event)
