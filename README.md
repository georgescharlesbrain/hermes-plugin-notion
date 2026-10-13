# hermes-plugin-notion

Notion comment collaboration for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

- **Gateway platform:** signed `comment.created` events are filtered without a model. Authorized addressed requests start turns in `notion:thread:<discussion_id>`; permitted follow-ups reuse the profile-local discussion session.
- **Tools:** `notion_get_comments` and `notion_reply_comment`, restricted to approved page/block roots. Replies are read back from the exact discussion before success is reported.
- **Shared code, local authority:** one canonical checkout serves Aroa and Greta through profile plugin symlinks. Credentials, trust, replay state and sessions are not shared.
- **Fail closed:** no approved humans or roots means no execution; no signing secret means HTTP 503. Public handshake replacement is refused.

## Guides

- [Human-agent collaboration contract](docs/collaboration-contract.md)
- [Agent operating guide](docs/agent-operations.md)
- [Security and deterministic routing](docs/security-routing.md)
- [Upgrade, profile-local migration, rollback and verification](docs/maintenance.md)
- [Historical handover / evidence](HANDOVER.md)

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

## Verified host facts (2026-10-13)

- Canonical checkout: `/home/hermes/.hermes/plugins/notion`, baseline `main` at `a20b231`.
- Greta plugin symlink resolves to that checkout.
- Default/Aroa `plugins.enabled` excludes Notion; Greta's includes it.
- Neither inspected profile config has `platforms.notion` settings.
- Default Notion MCP is enabled; its read-only identity is human GCB in workspace GCB. Greta's MCP is configured disabled. **MCP authorization is separate from this plugin's REST bot connection.** REST bot identity and webhook subscription status were not verified.
- No local listener was present on port 8646; health request could not connect. Existing credentials were not displayed or changed. Candidate not deployed; no live Notion content mutated.

## Tests

From an isolated clone with the installed Hermes environment:

```bash
/usr/local/lib/hermes-agent/venv/bin/python -m pytest tests -q
```

Fake API tests exercise real ingress/routing/dispatch/send code, profile scopes, replay, filters and budgets; they do not prove live webhook delivery. Tests use scratch homes and fake credentials. Client API version remains `2022-06-28`; changing versions requires a separate compatibility exercise, not an untested string change.
