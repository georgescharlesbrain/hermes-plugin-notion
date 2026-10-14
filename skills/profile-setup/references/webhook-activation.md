# Activate a profile webhook

Use one connection and one subscription per profile.
In Notion's connection settings, check Webhooks: event type comment.created,
verified status, active versus paused state, and the exact profile endpoint.

For a new handshake, issue a profile-bound, single-use, expiring provisioning
ticket before creating the subscription. Put it in the endpoint query parameter
provision_ticket. The private operator setup file holds the ticketed URL.

Notion sends only verification_token in its handshake. It does not echo our
ticket ID or subscription ID. Do not require metadata that Notion cannot send.
Allow replacement of an existing stored token only through an explicit
operator-issued replacement ticket.

The plugin stores the received token under the receiving profile's plugin data.
The operator reads it and pastes it into Notion's Verify subscription form.
The agent must not print it. Use Resend token after checking the ticket.
Never place the token or ticketed URL in Asana or chat.

The verified token signs later events. A profile-local credential secret can
also supply the signing value. Check the effective loader, not just one file.
A signing mismatch returns 401. A verified signature with a foreign integration
ID returns 403. Do not remove either check to make a test pass.

After activation or resumption, add a new human comment on an approved page.
Check actual delivery and the resulting reply, not only a health request.
Official instructions: https://developers.notion.com/reference/webhooks
