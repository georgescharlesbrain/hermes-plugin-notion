# hermes-plugin-notion

Notion integration for [Hermes Agent](https://github.com/NousResearch/hermes-agent), as a standalone plugin.

- **`notion` gateway platform.** Receives Notion webhooks, verifies HMAC-SHA256 signatures (`X-Notion-Signature`), filters comment mentions deterministically, and dispatches agent turns.
- **`notion` toolset.** `notion_reply_comment` and `notion_get_comments`.
- **Deterministic routing.**
  - If `@greta` or `greta@ufahamu.xyz` is mentioned -> answer.
  - If another user is mentioned without Greta -> ignore.
  - If no user is mentioned -> answer.
  - If comment is authored by the bot integration -> drop (infinite loop guard).
- **Inactivity guard.** Inactive in any profile where `NOTION_API_TOKEN` is not configured.

## Configuration

Credentials in `~/.hermes/profiles/<profile>/.env`:

```env
NOTION_API_TOKEN="ntn_..."
NOTION_KEYRING=0
NOTION_WEBHOOK_SECRET="secret_..."
```

Enable plugin in profile `config.yaml`:

```yaml
plugins:
  enabled:
    - notion
```
