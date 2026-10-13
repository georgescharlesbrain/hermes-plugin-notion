# Security and deterministic routing

## Threat boundary

Public ingress is untrusted. Signed webhook metadata proves possession of the subscription's signing secret, not human intent. The authoritative comment is retrieved from Notion using the receiving profile's captured connection. Only immutable configured human IDs can authorize execution; display names and emails are not grants. Peer bot authors are denied, and own integration and bot-user IDs are suppressed before the allowlist.

Page/block content is untrusted evidence. Prompt delimiters make this distinction visible but do not prevent model prompt injection or constrain shell/MCP access. Profiles sharing one Unix account are operational isolation, **not an adversarial security sandbox**. A tool-capable process with filesystem access may inspect another profile unless host policy prevents it.

## Decision table (no model used)

| Input | Decision |
|---|---|
| Foreign profile path | HTTP 404, no fallback to default |
| Public verification handshake | HTTP 403; never replaces/logs/echoes secret |
| No provisioned signing secret | HTTP 503 |
| Missing/bad signature | HTTP 401 |
| Configured integration ID mismatches signed event | HTTP 403 |
| Own integration ID or own bot user ID | Ignore, even if allowlisted |
| Unknown human; email/name-only match | Ignore |
| Any bot/peer integration | Ignore; no autonomous handoff |
| Request over 8192 characters | Ignore: request budget exceeded |
| Optional agent prefix then `FYI:`, `status:`, `update:` | Ignore: non-actionable update |
| Exact terminal acknowledgment/reaction text | Ignore; mixed acknowledgments plus instructions are not discarded |
| `stop`, `cancel`, `pause` after optional agent prefix | Close future implicit continuation |
| True user mention with different ID, even matching display name | Ignore: addressed to other user |
| Literal target prefix or exact configured bot-user mention | Eligible for scope and budget checks |
| Target only mentioned mid-sentence | Ignore: topic, not address |
| No address, previously owned discussion, configured human | Eligible continuation |
| No address, unowned/stopped discussion | Ignore |
| Missing discussion/comment/author/text | Ignore |
| Parent outside approved roots or ancestry lookup fails/cycles | No dispatch or plugin-tool write |
| Duplicate comment ID | No second execution |
| Non-`comment.created` event | Ignore |

Prefix filters are explicit conventions, not an NLP classifier. The router cannot infer unlimited semantic intentions from prose. Explicitly addressed statements without FYI/status markers may therefore be requests; humans should mark no-action material.

## Isolation

- Settings and tools use Hermes' scoped-secret API, not process-global credential reads.
- Default home is labeled `aroa`; named `greta` home is labeled `greta`. Foreign explicit labels and unknown profiles are rejected.
- Each adapter captures its settings and state home when created. Handler, background processing and outbound replies bind that home through a context override. Replies cannot select another profile from metadata.
- Storage resolves `get_hermes_home()`; executor calls inherit task context. Shared code symlinks do not point state at the shared checkout.
- Only the current adapter's generic/configured path and own named path are installed. The old path substring selector is retained as an unused compatibility helper, not a routing authority. A future central dispatcher must resolve a live peer adapter and enter its full runtime before authentication/spawning; this candidate intentionally does not provide cross-profile dispatch.

## Bounds and replay

32 pending events maximum, serialized dispatch, 1 MiB body, 8192 request characters, 4096 context characters and a 300-second awaited callback limit. A 3-second outgoing cooldown and 5 replies per discussion per minute trip a latched breaker. Comments are atomically claimed in local SQLite `replay.db` before callback dispatch, with no ID eviction. Legacy processed-comment JSON remains honored and is not rewritten. Corrupt legacy replay state raises instead of silently forgetting it.

At-most-once execution trades recovery for safety: a crash after claiming requires a fresh human request. SQLite replay claims are transactional across processes; discussion ownership, parent bindings and reply counters remain legacy JSON and are not a cross-process transactional ledger. Run one active adapter process per profile. Do not treat the JSON cooldown as an atomic budget across multiple concurrent tool senders.

The callback timeout is **not a verified downstream model/tool-call cap**. Hermes may queue work beyond callback return; cancelling a coroutine cannot undo completed writes or recall injected work. Per-turn tool budgets, durable reply reservations and revocation checks on downstream queue execution are separate follow-up work.

## Permission enforcement limits

The plugin checks ancestry to an approved page/block root, up to 32 levels, refusing lookup failures. It applies this to incoming context, comment listing, and bound-discussion replies. A root-ID match is an operator grant; roots must be verified in the right workspace before configuration. The current ancestry helper uses block retrieval: unsupported database/data-source ancestry fails closed rather than broadening access.

This does not wrap independent Notion MCP, direct HTTP/CLI, browser, terminal or generic page-creation tools. An automated turn with those tools can bypass plugin-root constraints. Rollout must select a restricted tool surface or add a host-wide Notion write gate before calling this a workspace permission system. No free-child-page role grant is enabled by this candidate.

## Residual hardening proposals

1. Restricted automated-turn toolsets and a shared Notion mutation policy covering MCP and child-page roles.
2. Operator-authenticated, time-bounded webhook pairing; public pairing stays disabled in this candidate.
3. Validate connection bot/workspace identity read-only before startup; independently inspect subscription delivery/capabilities. Current `/users/me` REST identity was not probed.
4. Durable SQLite discussion/reply ledger with atomic cooldown reservations, exact returned-content readback, revocation epoch and safe failed-dispatch recovery.
5. Explicit ID format validation and modern Notion API-version compatibility coverage before migrating from `2022-06-28`.

See [maintenance](maintenance.md) for safe rollout and rollback. No new subscriptions, credential setup or permissions are requested as part of this review.
