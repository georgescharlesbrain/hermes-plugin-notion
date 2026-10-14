---
name: profile-setup
description: Set up a profile connection and debug webhook delivery.
version: 0.1.0
author: Koen (georgescharlesbrain), Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [notion, profiles, setup, webhooks, maintenance]
    related_skills: [use]
---

# Set up Notion for a Hermes profile

Use this skill for a new profile connection, webhook activation, verification,
or plugin maintenance. It replaces the broad notion-plugin-operations skill.
Use notion:use for ordinary workspace work and comments.

## When to use

- Add or verify the Notion connection for a configured Hermes profile.
- Configure page sharing, credentials and a webhook subscription.
- Diagnose missing comment replies or maintain the plugin deployment.
- Do not use a connection failure as permission to broaden access.

## Setup procedure

1. Check existing connection identity through the profile-scoped ntn wrapper.
2. Open https://www.notion.so/profile/integrations and select the correct connection.
3. Enable required read-content, read-comment and insert-comment capabilities.
4. Share only the approved pages. Configure immutable human IDs and roots.
5. Store the API token through the approved profile credential interface.
6. Configure a distinct listener path and port for the profile.
7. Create or inspect the webhook subscription. Select comment.created.
8. Confirm that it is verified and active, not paused.
9. Check the public route, signature enforcement and a real human comment.
10. Read back the reply in the original discussion before declaring readiness.

The plugin supports configured named profiles. New profiles require explicit bot identity,
mention names, authorized human IDs and allowed roots. They inherit no legacy permissions.
Keep each profile's credentials and plugin-data private. See docs/profile-setup.md for the
configuration example, peer addressing, compatibility defaults and setup verification.

Read the plugin's docs/profile-setup.md for the human setup instructions.
Read references/webhook-activation.md before creating or replacing a subscription.
Read references/maintenance.md before changing code or reloading the gateway.

## Credentials and identity

The API token and webhook signing secret are different credentials.
Use supported profile loaders. Never print credentials or put them in command
arguments, tasks, setup guides or screenshots.

Check both the profile credential store and the supported compatibility token
loader when determining whether an effective signing secret exists.
An absent compatibility file does not mean an absent secret.

A bot user ID, webhook integration ID, subscription ID and workspace ID have
different meanings. Configure the integration ID from verified connection or
signed-event metadata. Do not assume it equals the bot user ID.

## Delivery diagnosis

Check these layers separately: page/comment access, active subscription,
public routing, signature validation, integration-ID validation, routing,
session dispatch and reply readback.

A public 200 health response proves reachability only.
A signed synthetic request is not evidence of real Notion delivery.
An empty processing log is not proof that no HTTP request arrived.
Check Notion's delivery history or trusted proxy analytics, including origin
status and user agent. Real events may be rejected before processing is logged.

Read references/listener-diagnostics.md for response-code checks.
Preserve signature, profile, author and root checks while debugging.

## Verification

Record candidate, tested, committed, installed, loaded and live-tested states
separately. Give exact evidence without secrets.
Keep the Asana parent short and place results and blockers in subtasks.
Only the human completes tasks. Do not mark a deployment ready while replies
remain unverified.

## Pitfalls

Do not recreate a paused subscription when resuming it is sufficient.
Do not infer the tunnel source from a --config argument. Verify config_src and
the connector's effective configuration.
Do not restart a busy shared gateway or run sudo without the required approval.
