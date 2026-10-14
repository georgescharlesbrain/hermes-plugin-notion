# Notion integration maintenance

For initial setup and paused subscriptions, use [the Hermes profile setup guide](profile-setup.md).

Read [security and routing](security-routing.md) before rollout. This guide mirrors the Asana plugin's separation of shared implementation, profile-local settings/state, operations and collaboration policy.

## Inventory and connection checks

Never read operational credential files, print environment values or copy secret-bearing logs into reports. Existing authentication is configured; use connection metadata/status, not a new setup request.

```bash
hermes mcp list
readlink -f /home/hermes/.hermes/profiles/greta/plugins/notion
git -C /home/hermes/.hermes/plugins/notion status --short
git -C /home/hermes/.hermes/plugins/notion log -1 --oneline
ss -ltnp 'sport = :8646'
```

Notion MCP `notion_get_self` is a read-only check of the MCP workspace/user. It does **not** verify the REST bot identity used by the comment listener. A listener health response proves only a route is responding, not that a real signed comment reaches the correct Hermes profile.

## Shared-code upgrade (operator-approved only)

1. Work in `/home/hermes/.agents/tmp/aroa-notion-impl`, not the installed checkout. Review a dedicated pushed branch (`fix/profile-safe-collaboration`).
2. Run the complete plugin suite with the installed host venv (`/usr/local/lib/hermes-agent/venv/bin/python -m pytest tests -q`). Record branch/commit and test result.
3. Inventory every profile symlink to the canonical repo and its local config. Preserve all unknown operational files and existing sessions/cron/memory.
4. For each profile, back up config and `plugin-data/notion/` to an operator-controlled private location with restrictive permissions. Do not print backup contents.
5. Update installed checkout via clean fast-forward: `git -C /home/hermes/.hermes/plugins/notion pull --ff-only origin fix/profile-safe-collaboration`.
6. Restart only after explicit rollout approval and saved task/session state. A gateway restart can terminate the reporting session; the parent/operator performs it.

## Profile policy and identity configuration

- **Aroa**: Authorized by Koen (`a28331c7-f20f-48ea-8757-b6d3dd3e22fd`) with whole GCB workspace authority (`982fd186-4e7c-4435-ad62-bf23735bb30f`, bot ID `3f71c0e1-80e8-8148-8d4a-002761fd23b7`). Default `allowed_root_ids` resolves to `["*"]`.
- **Greta**: Restricted connection (`3f71c0e1-80e8-81bb-8268-002765b23008`). Default `allowed_root_ids` resolves to her 4 verified roots: `3f71c0e1-80e8-8076-be25-f9cadd5041bd`, `3f71c0e1-80e8-8057-a55f-cea070b2f488`, `3f71c0e1-80e8-8106-9516-fb873d6e5ade`, `3f71c0e1-80e8-81ea-9ae3-db37ead313d8`. Wildcard grants are forbidden.

## Authenticated expiring webhook provisioning

1. **Generate ticket**: Operator issues short-lived provisioning ticket bound to profile and subscription ID:
   `storage.create_provisioning_ticket(profile="aroa", subscription_id="sub-xxx", ttl_seconds=300, allow_replacement=False)`
2. **Deliver secret**: Notion webhook handshake or operator presents `provision_ticket` alongside `verification_token`.
3. **Validation**: Endpoint verifies ticket expiry, profile match, subscription match, and single-use claim atomically in SQLite.
4. **Rollback**: If provisioning fails or must be rolled back, delete or restore `secrets_<profile>.json` and clear ticket state in `replay.db`.

## Supported API versions and ancestry compatibility

- Baseline API version is `2022-06-28`.
- Modern ancestry resolution supports container types: `page_id`, `block_id`, `database_id`, `data_source_id`, and `workspace`.
- Unrecognized container types or malformed identifiers fail closed immediately.
- Migration limits: upgrading API version to `2025-09-03` requires preserving data source parent mapping.
