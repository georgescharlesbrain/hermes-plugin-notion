# Notion integration maintenance

Read [security and routing](security-routing.md) before rollout. This guide mirrors the Asana plugin's separation of shared implementation, profile-local settings/state, operations and collaboration policy; it does not claim Asana's CLI, assignment or handoff capabilities exist here.

## Inventory and connection checks

Never read operational credential files, print environment values or copy secret-bearing logs into reports. Existing authentication is configured; use connection metadata/status, not a new setup request.

```bash
hermes mcp list
readlink -f /home/hermes/.hermes/profiles/greta/plugins/notion
git -C /home/hermes/.hermes/plugins/notion status --short
git -C /home/hermes/.hermes/plugins/notion log -1 --oneline
ss -ltnp 'sport = :8646'
```

Notion MCP `notion_get_self` is a read-only check of the MCP workspace/user. It does **not** verify the REST bot identity used by the comment listener. A listener health response proves only a route is responding, not that a real signed comment reaches the correct Hermes profile. Check subscriptions in Notion's integration settings without changing them during review.

## Shared-code upgrade (operator-approved only)

1. Work in `/home/hermes/.agents/tmp/aroa-notion-<topic>`, not the installed checkout. Review a dedicated pushed branch; no PR is required for the review artifact.
2. Run the complete plugin suite with the installed host venv and `git diff --check`. Record branch/commit and test result.
3. Inventory every profile symlink to the canonical repo and its local config. Preserve all unknown operational files and existing sessions/cron/memory.
4. For each profile, back up config and `plugin-data/notion/` to an operator-controlled private location with restrictive permissions. Do not print backup contents. Record the installed commit and config revision.
5. Decide an ingress routing plan: separate live adapters and ports, or a reviewed Hermes shared-ingress integration. Never route another profile's path to the default adapter as a fallback.
6. Have the parent/operator approve and merge or cherry-pick the reviewed commit into the canonical branch. Update the installed checkout with a clean fast-forward; do not run destructive reset on unknown local files. Symlink users all receive this code upgrade, but none automatically receives trust, roots or new credentials.
7. Migrate each profile's non-secret settings through `hermes config set`. Keep existing authentication. Missing verified grants mean deny, not invented defaults.
8. Restart only after explicit rollout approval and saved task/session state. A gateway restart can terminate the reporting session; the parent/operator performs it, not the review subagent.
9. Verify each profile independently using the checklist below. No live Notion writes until a human-approved test page/discussion is identified.

## Profile-local migration

- Default home labels Aroa; named `greta` home labels Greta. No unknown-profile fallback. A foreign explicit `profile` label raises instead of choosing different credentials.
- Put verified immutable human IDs in `allowed_user_ids`. Old code's hardcoded names/emails and Aroa-to-Greta bot grant are intentionally removed. Do not copy another profile's trust list.
- Put only owner-approved page/block roots in `allowed_root_ids`. No family-role or page-root defaults are supplied.
- Record verified `bot_integration_id` and, where available, `bot_user_id`. Do not mistake historical integration IDs for newly verified bot-user identities.
- Maintain profile-specific `mention_names`, ingress route and local port. Generic ingress is local to the receiving adapter, not inherently Greta.
- State remains under the active home: `plugin-data/notion/discussions.json`, `discussion_parents.json`, `circuit_breaker.json`, legacy processed-comment JSON, signing-secret compatibility files, and new `replay.db`.
- SQLite replay state is additive: historical JSON is honored but not rewritten/deleted. IDs no longer expire at 1000 comments. Old discussion owners have no parent bindings; replies deny until a fresh permitted request establishes one.
- Public handshake storage is removed. Existing provisioned signing material continues to work. Creating a new subscription requires a separately secured operator provisioning workflow; no credential reconfiguration is needed for existing authentication.

## Verification after rollout

1. Confirm installed commit, canonical symlink targets and no unexpected diff.
2. Confirm each profile's plugin enablement, non-secret routing fields, intended empty/nonempty trust and root lists; never print credentials.
3. Confirm the live listener and health route for **each** profile's configured port. Wrong-profile paths must be 404; bad signatures 401; absent signing material 503; handshake replacement 403.
4. On an explicitly approved disposable discussion, have a configured human address one agent with a bounded question. Verify one turn, correct profile session, exact original `discussion_id`, and exact reply readback. Repeat for the other profile; the first profile must neither answer nor receive state writes.
5. Verify FYI/status/ack, unknown author, own bot, peer bot, mid-sentence mention and duplicate-event cases do not execute. Do not forge production events or replay genuine events without test authorization.
6. Check reply budgets and stopped continuation on disposable discussions. Verify future re-addressing deliberately reopens work. Record that active/queued turn cancellation is not guaranteed.
7. Verify independent MCP/page tools are restricted before enabling automated mutation-capable turns. Plugin root checks alone are not a universal permission gate.

## Rollback

Pause or disable ingress before rollback. Restore the recorded code revision through a reviewed revert or operator-approved checkout; restore settings through the configuration CLI. Preserve new replay SQLite state, parent bindings and unknown files. Do not delete newer replay claims merely to make old code run.

**Security downgrade warning:** baseline `a20b231` accepts unsigned events without a secret, lets public handshakes replace secrets and authorizes display-name substrings. Do not expose that baseline publicly as a rollback strategy. Prefer reverting the feature with ingress disabled, or a security-only patch. Old code does not consult SQLite claims, so reopening baseline ingress can replay already-executed comments. Review/export a private replay migration before any old-version activation.

## Cleanup candidates, not deletion orders

`HANDOVER.md` formerly described a temporary live runner and an incorrect Greta path; it is now superseded. An unused path-selector helper and historical identity constants remain for compatibility/tests, not grants. Legacy JSON and provisioned signing files may contain necessary state: archive only after verified migration, never delete from this review. No temporary runner was found listening on 8646 during review.
