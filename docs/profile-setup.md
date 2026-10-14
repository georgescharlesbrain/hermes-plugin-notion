# Set up Notion for a Hermes profile

Use one Notion connection and one webhook subscription for each Hermes profile.
Aroa and Greta share plugin code. They do not share API tokens, signing secrets,
permissions or sessions.

If a connection already exists, check it before creating another one.
An active connection does not prove that its webhook subscription is active.

## 1. Select the connection

Open [Notion connection settings](https://www.notion.so/profile/integrations).
Select the connection for the Hermes profile, or create an internal connection
in the required workspace.

On this server, the existing connections are:

| Hermes profile | Notion connection |
| --- | --- |
| Aroa, default Hermes home | aroa \| pa koen |
| Greta, named Greta home | greta \| family manager \| house manager |

Enable the capabilities needed to read content, read comments and insert comments.
Share only the approved pages with that connection through the page's
Connections menu. Do not enlarge Greta's access to make a test pass.

See [Notion's connection setup instructions](https://developers.notion.com/docs/create-a-notion-integration).

## 2. Store the connection key securely

The connection's API token lets the profile read Notion and insert replies.
Store it in that profile's Hermes credential store through the approved
credential setup interface. If an operator configures it for you, transfer it
through an approved secret channel, not a comment or this chat.

The plugin resolves `NOTION_API_TOKEN_AROA` or `NOTION_API_TOKEN_GRETA` first.
A profile-local `NOTION_API_TOKEN` is the fallback.
The separate Notion CLI and MCP login do not configure the plugin's REST token.

Do not put the token in a repository, Asana task, setup guide or screenshot.
Do not ask an agent to print it. Check the bot's identity through
`/v1/users/me` using the selected profile's supported credential loader.

Configure the profile's approved human IDs, page roots, bot user ID, webhook
integration ID, listener port and endpoint. The webhook integration ID comes
from the connection or subscription metadata. Do not infer it from a bot user
ID. Keep all existing profile permissions unless the operator approves a change.

## 3. Set up the webhook subscription

A webhook tells Hermes that a new comment exists. The API token alone does not
send these notifications.

In the selected connection's **Webhooks** tab:

1. Check whether the subscription already exists.
2. Check whether it is verified and active, not paused.
3. Check whether `comment.created` is selected.
4. Check whether it points to this profile's endpoint.
5. If setup is missing, create the subscription and complete verification.

These are the public paths on this server:

| Profile | Public endpoint | Local listener |
| --- | --- | --- |
| Aroa | https://webhooks.georgescharlesbrain.com/webhooks/notion/aroa | 127.0.0.1:8646 |
| Greta | https://webhooks.georgescharlesbrain.com/webhooks/notion/greta | 127.0.0.1:8648 |

For a new subscription or a verification-token replacement, the operator must
first issue a single-use, expiring provisioning ticket. Use the ticketed URL
from the private setup file, not just the bare endpoint above. On this server,
the operator's setup file is `/home/hermes/notion-webhook-setup.md`.
Check ticket expiry before use. Never publish its ticket URLs.

Notion sends a verification token to that endpoint. The plugin stores it for
the correct profile. The operator reads the stored value and pastes it into
Notion's **Verify subscription** form. Use **Resend token** if necessary.

The webhook verification token is the signing secret. It is not the API token.
The plugin also supports a profile-local `NOTION_WEBHOOK_SECRET`, with
`NOTION_WEBHOOK_SECRET_AROA` or `NOTION_WEBHOOK_SECRET_GRETA` taking precedence.
A missing compatibility token file does not prove that no signing secret exists.

Do not recreate a verified subscription merely because it was paused.
Resume it and test a new comment first.

See [Notion's webhook setup and verification instructions](https://developers.notion.com/reference/webhooks).

## 4. Check the server route

Check the actual tunnel configuration source through Cloudflare and the running
connector's logs. A local configuration file alone does not establish the source.

On 14 October 2026, this server's tunnel reports `config_src: cloudflare`.
The connector receives the remote configuration even though its command names
a local file. Keep the Greta-specific route above the broad Notion route.
Preserve other routes and a private backup before changing either configuration.

A GET on each public endpoint must identify the correct profile.
An unsigned POST must return 401. These checks prove reachability and signature
enforcement. They do not prove a verified, unpaused Notion subscription.

## 5. Test a new human comment

After resuming or verifying the subscription, create a new comment on a page
shared with the selected connection:

- `Aroa, reply with AROA-OK`
- `Greta, reply with GRETA-OK`

Test the profiles separately. Each reply must appear once in its original
discussion. Use the literal name prefix. A connection need not appear in
Notion's human mention picker.

Check the webhook delivery history in Notion and the gateway logs on the server.
Read back the reply through the correct profile's API. Do not call the setup
complete until a real signed event produces the correct reply.

## If no reply appears

| Check | Meaning and next action |
| --- | --- |
| The comment is visible through the profile API | Page access and comment-read capability work. This does not prove webhook delivery. |
| No delivery appears in Notion | Check active versus paused status, the subscribed event, and the page connection. |
| Notion reports 401 | Check the subscription's signing token against this profile's effective secret. Do not print either value. |
| Notion reports 403 | Check the endpoint profile, webhook integration ID, or provisioning-ticket failure. |
| Notion reports 404 | Check the exact endpoint path and tunnel route order. |
| Notion reports 503 | The listener has no effective signing secret. Provision the correct profile. |
| Notion reports 200 but no turn starts | Check event type, comment ID, author authorization, addressing, replay and stop state. |
| A turn starts but no reply appears | Check model errors, reply permissions, cooldown and reply budgets. Read the discussion before retrying. |

The remote plugin cannot infer Notion's paused state from an API token or a
health response. Obtain the subscription status and delivery result from
Notion's Webhooks tab. Keep tokens and URL query parameters out of screenshots
and reports.

See [the collaboration rules](collaboration-contract.md),
[security and routing](security-routing.md), and [maintenance](maintenance.md).
