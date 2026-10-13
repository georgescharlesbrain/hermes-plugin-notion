# Notion plugin handover

The previous handover described historical hardcoded caller grants, unverified connection identities, a temporary runner, and permissive cross-profile ingress. It is superseded by:

- [README: overview, supported settings and verified host facts](README.md)
- [Human-agent collaboration contract](docs/collaboration-contract.md)
- [Agent operating guide](docs/agent-operations.md)
- [Security, answer/ignore routing and residual risks](docs/security-routing.md)
- [Upgrade, migration, rollback and verification](docs/maintenance.md)

## Review evidence

Baseline `main` at `a20b231`: 27 tests passed before changes. New regression tests first reproduced display-name authorization, unsigned ingress, unauthenticated secret replacement, foreign-profile routing, unknown-profile fallback, process-global credential resolution and state-home leakage. Further red/green cycles cover scope refusal, stop/filter decisions, pagination, callback/pending budgets and durable replay claims.

Shared canonical checkout is `/home/hermes/.hermes/plugins/notion`; Greta's symlink is `/home/hermes/.hermes/profiles/greta/plugins/notion`. The old path missing `.hermes` was incorrect. No local listener was found on 8646 during review. The default MCP identity was checked read-only; REST bot identity and live comment delivery were not tested. Existing authentication was neither requested again nor changed.

The candidate is a pushed review branch, not deployed code. No restart, live content mutation, new root grants or human trust additions were performed. Parent/operator must independently review and approve rollout, especially the independent MCP mutation boundary and profile-local ingress setup.
