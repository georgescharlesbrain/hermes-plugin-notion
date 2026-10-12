# Notion Hermes Plugin — Handover Documentation

This document describes the design, configuration, safety layers, and operational status of the Notion integration plugin for Hermes Agent (`hermes-plugin-notion`).

---

## 1. Executive Summary

The `notion` plugin connects Notion comment threads to Hermes agent profiles via Notion REST webhooks and HMAC SHA-256 signatures. It enables bidirectional collaboration where humans and bots comment on Notion pages and blocks, and bots reply back into the discussion thread.

The integration supports two distinct agent personas:
1. **Aroa (`aroa`)**: Personal Assistant to Koen.
2. **Greta (`greta`)**: House Manager and Family Manager.

---

## 2. Architecture & File Structure

Repository: `https://github.com/georgescharlesbrain/hermes-plugin-notion`
Installation directory on `hetzner-hermes`: `/home/hermes/.hermes/plugins/notion`
Symlink for profile `greta`: `/home/hermes/profiles/greta/plugins/notion`

```text
hermes-plugin-notion/
├── __init__.py                # Plugin package entrypoint
├── plugin.yaml                # Hermes plugin specification
├── README.md                  # Basic plugin usage
├── HANDOVER.md                # This comprehensive engineering handover
├── hermes_notion/
│   ├── __init__.py
│   ├── adapter.py             # Hermes BasePlatformAdapter (aiohttp webhook listener + sender)
│   ├── router.py              # Pure routing logic, authorization, topic detection, and parsing
│   ├── storage.py             # Verification tokens, deduplication cache, circuit breaker, thread state
│   ├── settings.py            # Profile configurations (Aroa vs Greta) and environment loaders
│   └── notion_client.py       # Standard library HTTP client for Notion REST API v1
└── tests/
    ├── test_adapter.py        # Token validation, path routing, signature verification
    ├── test_notion_client.py  # Block text extraction and payload builder tests
    ├── test_router.py         # 17 comprehensive routing, authorization, and loop guard tests
    └── test_storage.py        # Deduplication, cooldown, and circuit breaker tests
```

---

## 3. Identifiers & Authorization Registry

### Identities

- **Koen (GCB)**:
  - User ID: `a28331c7-f20f-48ea-8757-b6d3dd3e22fd`
  - Email: `georges.charles.brain@gmail.com`
  - Names: `GCB`, `Koen`
- **Qaren (Karen)**:
  - Emails: `haelnerac@gmail.com`, `qaren@ufahamu.xyz`
  - Names: `Qaren`, `Karen`
- **Aroa**:
  - Bot Integration ID: `3f71c0e1-80e8-8148-8d4a-002761fd23b7`
  - Mention User: `aroa`, `aroa@ufahamu.xyz`
- **Greta**:
  - Bot Integration ID: `3f71c0e1-80e8-81bb-8268-002765b23008`
  - Bot User ID (Notion mention user): `3f7d872b-594c-8120-9081-000252622a03`
  - Mention User: `greta`, `greta@ufahamu.xyz`

### Caller Authorization Matrix (`router.py:ALLOWED_CALLERS`)

| Target Bot | Allowed Callers | Denied Callers | Rationale |
| :--- | :--- | :--- | :--- |
| **Aroa** | Koen (`GCB`) | All other humans, all bots (including Greta) | Aroa is Koen's confidential personal assistant. No other entity may command Aroa. |
| **Greta** | Koen, Qaren, Aroa | All other users and unknown bots | Greta is the house/family manager. Aroa can delegate family tasks to Greta. |

---

## 4. Loop Prevention & Safeguard Layers

To prevent infinite loops between bots or cascading webhook storms, the plugin implements 8 defense-in-depth safety layers:

### Layer 1: Self-Bot Drop (`router.py`)
A bot **never** responds to a comment authored by itself:
`comment.created_by.id == settings.bot_integration_id` -> Dropped with `authored_by_target_bot`.

### Layer 2: Caller Authorization Registry (`router.py`)
If the comment author is not in `ALLOWED_CALLERS[target_bot]`, it is dropped immediately with `author_not_authorized`.
*Because Aroa can address Greta, but Greta cannot address Aroa, bot-to-bot interactions cleanly terminate at Greta.*

### Layer 3: Terminal Acknowledgment Filter (`router.py`)
Gratitude or acknowledgment phrases without instructions or questions (`"thank you"`, `"thanks"`, `"got it"`, `"noted"`, `"cool"`, `"all good"`, `"great"`) close the conversation turn. They are dropped with `terminal_acknowledgment`.

### Layer 4: Start-of-Comment Addressing (`router.py`)
- If a comment starts with `@<bot>` or `<Bot>, ...`, the target bot processes it (`addressed_at_start`).
- If another bot or human is addressed at the start (`@someone`), the bot drops it (`addressed_to_other_user`).
- If the bot is mentioned in the middle of a sentence (e.g. *"I discussed this with Greta yesterday"*), it is treated as a discussion topic and dropped (`mentioned_as_topic_not_addressed`).

### Layer 5: Thread Ownership Continuation (`router.py` + `storage.py`)
When a comment has no `@mention` at the start:
- If the comment belongs to a discussion thread previously owned by this bot (`storage.get_discussion_owner`), the bot answers (`thread_continuation`).
- If no bot owns the thread, or another bot owns it, the comment is dropped (`not_addressed`).

### Layer 6: Webhook Idempotency & Deduplication (`storage.py`)
Notion webhooks operate with *at-least-once* delivery. Comment IDs are cached in `~/.hermes/plugin-data/notion/processed_comments.json`. Duplicate webhook deliveries are ignored immediately (`already_processed`).

### Layer 7: Event Type Filter (`adapter.py`)
The adapter only processes `comment.created` events. Non-creation events like `comment.updated` (user fixing a typo) are skipped to prevent duplicate responses.

### Layer 8: Velocity Circuit Breaker & Cooldown (`storage.py`)
- **3-Second Minimum Cooldown:** No bot can reply twice to the same discussion thread within 3 seconds (`thread_cooldown_active`).
- **Sliding-Window Velocity Breaker:** If more than 5 bot replies occur in the same thread within 60 seconds, the circuit breaker trips (`velocity_breaker_tripped`). Automated replies on that discussion thread are permanently locked until manual reset via `storage.reset_circuit_breaker(discussion_id)`.

---

## 5. Rich Selection Context Extraction

When a user highlights text on a Notion page and clicks "Comment":
- Notion attaches the comment to `parent.block_id`.
- The comment itself only contains the user's remark (e.g. `@aroa summarize this`).
- The adapter fetches the referenced block via Notion REST API (`GET /v1/blocks/{block_id}`) and extracts its plain text via `notion_client.extract_block_text(block)`.
- The prompt injected into Hermes Agent includes both the referenced page text and the user comment:
  ```text
  Notion comment from GCB referencing page text:
  > Here you can create new pages for research topics.

  Comment:
  @aroa summarize this

  [Discussion ID: ... | Comment ID: ...]
  ```

---

## 6. Endpoints, Tokens & Secrets

### Webhook URLs
Incoming webhooks hit Cloudflare and proxy to local port `8646`:
- Greta: `https://webhooks.georgescharlesbrain.com/webhooks/notion/greta`
- Aroa: `https://webhooks.georgescharlesbrain.com/webhooks/notion/aroa`
- Generic: `https://webhooks.georgescharlesbrain.com/webhooks/notion`

### Environment Variables
- `NOTION_KEYRING=0` (Present in all `.env` files to disable local keyring prompts)
- **Aroa (`/home/hermes/.hermes/.env`)**:
  - `NOTION_API_TOKEN=ntn_*** (see ~/.hermes/.env)`
  - `NOTION_WEBHOOK_SECRET=secret_*** (see ~/.hermes/.env)`
- **Greta (`/home/hermes/.hermes/profiles/greta/.env`)**:
  - `NOTION_API_TOKEN=ntn_*** (see ~/.hermes/profiles/greta/.env)`
  - `NOTION_WEBHOOK_SECRET=secret_*** (see ~/.hermes/profiles/greta/.env)`

Verification tokens received during webhooks are also saved to `~/.hermes/plugin-data/notion/secrets.json` and `secrets_aroa.json`.

---

## 7. Verification & Testing

### Running the Test Suite
The full test suite contains 27 unit tests across all components.

```bash
ssh hetzner-hermes "PYTHONPATH=/home/hermes/.hermes/plugins/notion:/usr/local/lib/hermes-agent /usr/local/lib/hermes-agent/venv/bin/pytest /home/hermes/.hermes/plugins/notion/tests"
```

All 27 tests must pass (100% pass rate).

### Checking the Live Test Runner
A standalone test runner runs on port 8646 to verify live webhook traffic without invoking full LLM inference:

```bash
# Check port status
ssh hetzner-hermes "lsof -i :8646"

# Check test runner logs
ssh hetzner-hermes "tail -n 50 /home/hermes/.agents/tmp/live_test_runner.log"

# Test health checks
curl -s https://webhooks.georgescharlesbrain.com/webhooks/notion/greta
curl -s https://webhooks.georgescharlesbrain.com/webhooks/notion/aroa
```

---

## 8. Next Steps for Incoming Model

1. **Production Hermes Gateway Integration**:
   - Currently, `live_test_runner.py` is running on port 8646 as a temporary standalone server.
   - To have Hermes AI models answer comments dynamically, enable `notion` under `plugins.enabled` in `/home/hermes/.hermes/config.yaml` and `/home/hermes/.hermes/profiles/greta/config.yaml`.
   - Stop `live_test_runner.py` and restart `hermes-gateway.service` so Hermes Gateway binds port 8646 natively.
2. **Resuming Notion Webhook Subscriptions**:
   - Webhook subscriptions in the Notion Developer portal were paused during testing.
   - With all 8 safety layers, circuit breakers, and deduplication now in place, the subscriptions are ready to be resumed.
3. **Multi-Agent Collaborative Delegation**:
   - When a user asks Aroa to delegate to Greta, Aroa posts a comment starting with `@greta`.
   - Verify that Greta receives Aroa's comment and successfully replies in the thread without creating an infinite loop.
