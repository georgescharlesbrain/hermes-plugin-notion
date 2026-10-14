# hermes-plugin-notion

Notion comment collaboration for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

- **Gateway platform:** signed `comment.created` events are filtered without a model. Authorized addressed requests start turns in `notion:page:<page_id>`; all discussions on a page reuse that profile-local page session. Discussion ownership and reply targets remain separate.
- **Tools:** `notion_get_comments` and `notion_reply_comment`, restricted to approved page/block roots. Replies are read back from the exact discussion before success is reported.
- **Shared code, local authority:** one canonical checkout serves Aroa and Greta through profile plugin symlinks. Credentials, trust, replay state and sessions are not shared.
- **Fail closed:** no approved humans or roots means no execution; no signing secret means HTTP 503. Public handshake replacement is refused.

## Guides

- [Set up Notion for a Hermes profile](docs/profile-setup.md): connection settings, secure keys, page access, webhook verification, paused subscriptions and a real comment test.
- [Human-agent collaboration contract](docs/collaboration-contract.md)
- [Agent operating guide](docs/agent-operations.md)
- [Security and deterministic routing](docs/security-routing.md)
- [Upgrade, profile-local migration, rollback and verification](docs/maintenance.md)
- [Use Notion](skills/use/SKILL.md), available as `notion:use`: profile-scoped ntn workspace work and bounded comment collaboration.
- [Set up a Hermes profile](skills/profile-setup/SKILL.md), available as `notion:profile-setup`: connections, webhooks, verification and maintenance.

## Notion is not Asana

A Notion connection is a bot/integration identity, not a full human user with an Asana-style assignee. Do not assume it appears in the human `@mention` picker. Start a comment with literal `Aroa, ...`, `@aroa ...`, `Greta, ...`, or `@greta ...`; these strings are routing conventions, not proof of a real Notion mention.

A human can select text and create a discussion in Notion. The API can reply to its existing `discussion_id`; it cannot create a new selected-range discussion. Context extraction retrieves the parent block (up to 4096 characters), **not necessarily the exact highlighted substring**. Replies stay in the original discussion. Access and read/insert-comment capabilities are required.

Official references: [create a comment](https://developers.notion.com/reference/create-a-comment), [comment object](https://developers.notion.com/reference/comment-object), [comment.created event](https://developers.notion.com/reference/webhooks/comment-created), [webhook signatures](https://developers.notion.com/reference/webhooks).

## Supported configuration

Settings live at `platforms.notion.extra`; change them with `hermes config set`, never hand-edit operational YAML. Existing authentication is already configured on the reviewed host: do not request or recreate it. Secret values are never needed by the agent.

```yaml
plugins:
  enabled: [notion]  # merge with existing enabled plugins
platforms:
  notion:
    enabled: true
    extra:
      profile: aroa  # default home = aroa; named greta home = greta
      host: localhost
      port: 8646
      webhook_path: /webhooks/notion
      bot_integration_id: "<verified webhook integration ID>"
      bot_user_id: "<verified bot user ID, if available>"
      mention_names: [aroa, aroa@ufahamu.xyz]
      allowed_user_ids: []  # verified humans, never names/emails/bots
      allowed_root_ids: []  # explicitly approved page/block roots
```

Empty lists deny execution; they are not proposed permissions. No page roots or new humans are activated by this repo. Unknown profiles and mismatched runtime labels are refused. Use a distinct local port per listener; reverse-proxy each named ingress to its own adapter. Each adapter accepts only its configured generic route and its own `/webhooks/notion/<profile>` route, never a cross-profile relay.

Credential resolution uses Hermes' scoped-secret API. Profile-suffixed values precede profile-local generic values; a provisioned local signing-secret file remains a compatibility fallback. See [the exact credential names and loader](hermes_notion/settings.py). The separate Notion CLI's keyring setting does not affect this adapter. Credentials are excluded from settings representations.

## Fixed safety limits

8192 request characters; 4096 parent-block context characters; 1 MiB HTTP body; 32 pending events per adapter; serialized dispatch; 300-second **dispatch callback** timeout; 3-second reply cooldown; 5 replies per discussion per 60 seconds before a latched breaker. This is not a Hermes-wide model/tool-call spending cap: downstream queued work can outlive the callback. See the security guide for residual limits.

## Connection verification and installation boundary (2026-10-13)

The bullets below record the initial review snapshot, not the current deployment. For current setup and readiness checks, use [the profile setup guide](docs/profile-setup.md). An API identity or an active listener does not establish the webhook subscription's paused state.

- Shared canonical checkout: `/home/hermes/.hermes/plugins/notion`; Greta's `/home/hermes/.hermes/profiles/greta/plugins/notion` symlink resolves there. Baseline was `main` at `a20b231`. Controlled installation of the reviewed branch is separate from gateway reload; verify the exact installed SHA with Git before reporting active behavior.
- Existing approved profile loaders plus `ntn api v1/users/me` independently authenticated both REST bots in workspace GCB (`982fd186-4e7c-4435-ad62-bf23735bb30f`). Aroa: `aroa | pa koen`, bot user `3f71c0e1-80e8-8148-8d4a-002761fd23b7`. Greta: `greta | family manager | house manager`, bot user `3f71c0e1-80e8-81bb-8268-002765b23008`.
- Historical Greta identifier `3f7d872b-594c-8120-9081-000252622a03` resolves to a **person** (`greta@ufahamu.xyz`), not the REST integration bot. Do not grant that identity human authority merely because its type is person or configure it as the bot user.
- Complete paginated search exposed 3537 unique objects to Aroa and four to Greta. These are connection-visible objects, **not a complete workspace inventory**. Exact retrieval verified Aroa can read Georges-Charles Brain, Private Second Brain and Aroa pages databases. Greta can read the house manager and family manager pages databases and their two responsibilities pages; retrieval of the three broader databases and Online Store failed under Greta's own credentials.
- Koen explicitly authorized Aroa's whole-GCB access. That authorization does not imply every page is already shared, and does not enlarge Greta's existing Notion sharing or role.
- Default Notion MCP is enabled; Greta's remains disabled. MCP's human OAuth identity is separate from the profile REST bots.
- Profile-local ingress configuration is staged **disabled**, with verified bot-user IDs and empty human/root grants. The webhook integration-ID field remains blank until verified from subscription metadata rather than inferred from `users/me`. No webhook was enabled, subscribed, or re-provisioned; no gateway restart was performed. Default plugin enablement remains a separate activation step.
- Credentials and existing script/auth/state were not changed. No Notion workspace content was created, updated or deleted. Human documentation belongs in this shared repository, not in Notion workspace pages.

See [maintenance](docs/maintenance.md) for test-first review evidence and pending rollout gates.

## Tests

From an isolated clone with the installed Hermes environment:

```bash
/usr/local/lib/hermes-agent/venv/bin/python -m pytest tests -q
```

Fake API tests exercise real ingress/routing/dispatch/send code, profile scopes, replay, filters and budgets; they do not prove live webhook delivery. Tests use scratch homes and fake credentials. Existing reads and creates retain API version `2022-06-28`. Comment replacement uses the verified `PATCH /comments/{comment_id}` endpoint with version `2026-03-11`.
