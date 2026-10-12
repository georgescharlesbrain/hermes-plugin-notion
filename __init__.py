"""Notion integration for Hermes.

Registers:
- the ``notion`` gateway platform: Notion comment webhooks in, one agent session per discussion thread (``hermes_notion.adapter``);
- the ``notion`` toolset: ``notion_reply_comment``, ``notion_get_comments``;
- deterministic @greta mention routing and loop guard.

Configuration lives in ``platforms.notion`` of ``config.yaml``, credentials in ``.env``.
"""

from __future__ import annotations


def register(ctx) -> None:
    from .hermes_notion import adapter, tools

    adapter.plugin_context = ctx
    ctx.register_platform(
        name=adapter.PLATFORM_NAME,
        label="Notion",
        adapter_factory=adapter.NotionAdapter,
        check_fn=adapter.check_requirements,
        is_connected=adapter.is_connected,
        required_env=["NOTION_API_TOKEN"],
        install_hint="pip install aiohttp",
        emoji="📝",
        allow_update_command=False,
    )
    for name, schema in tools.SCHEMAS.items():
        ctx.register_tool(
            name=name,
            toolset=tools.TOOLSET,
            schema=schema,
            handler=tools.HANDLERS[name],
            check_fn=tools.check_requirements,
            emoji="📝",
        )
