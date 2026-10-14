# Diagnose listener and delivery failures

| Evidence | Check |
| --- | --- |
| check_fn raised outside a profile scope | Use the supported scoped-secret reader with profile fallback. Keep requirements checks free of writes. |
| Generic pip install aiohttp hint | Inspect the actual requirements failure. The hint does not prove a missing dependency. |
| No registered adapter or no port | Check plugin discovery, manifest and the startup log. |
| Code or platform configuration newer than gateway startup | Plan an approved idle restart. Installed code is not loaded code. |
| Local 200, public 404 | Inspect ordered tunnel rules and the exact endpoint path. |
| Notion POST gets 401 | Verify this subscription's effective signing secret. Never print it. |
| Notion POST gets 403 | Check profile and integration-ID validation, or a rejected provisioning handshake. |
| Notion POST gets 503 | No effective signing secret is available to that listener. |
| Notion POST gets 200, no model turn | Inspect event type, comment ID, human authorization, addressing, replay, stop and queue budget. |
| Turn starts, no reply | Inspect model failure, write permission, readback and reply budgets. |

Health is a GET on /webhooks/notion/<profile>, not /health.
Compare a local health check with the public endpoint. The expected response
identifies the receiving profile. Unsigned POST must return 401 when a signing
secret is present.

Check the configured platform set against the gateway's running platform set.
Use startup logs and actual listeners, not configuration alone.
Duplicate top-level and platforms.notion.extra values are a finding; do not
change them outside the approved task.

The tunnel can be local-managed or Cloudflare-managed. Read config_src and
effective connector logs. A remote configuration can override a local file
named in the process command. Ingress rules use first-match order; a narrow
profile route must precede the broad Notion route.

An empty application processing log is inconclusive. Distinguish actual
notion-api requests from curl and synthetic diagnostics through delivery history
or trusted proxy analytics. Record edge and origin status separately.
Do not record request bodies, signatures, secrets or URL query parameters.
