# Profile-scoped NTN workspace commands

During automated Notion turns, use notion_ntn(args=[...], body={...}, stdin="...").
This tool executes the installed NTN CLI without a shell, binds the active Hermes
profile and keeps its credentials/cache/mutation ledger private. It supports api,
pages, datasources, files, whoami and help. It does not expose login, auth, workers,
local file inputs, process environment overrides, terminal or Notion MCP.

Outside automated comment turns, use terminal with scripts/ntn_profile.py and
Hermes' Python runtime for approved workspace work. Do not put a token in arguments.

## Requests

GET is the default. A body selects POST unless -X specifies the method.
For API writes, pass JSON in body. name==value query arguments remain supported.
Do not combine body with --data. Local --data @path, --file and --filter-file inputs
are refused. Use literal Markdown stdin or --content for high-level page commands.

Examples of args, without the ntn executable:
- ["api", "v1/users/me"]
- ["api", "v1/pages/<page-id>"]
- ["api", "v1/blocks/<block-id>/children", "page_size==100"]
- ["api", "v1/comments", "block_id==<block-id>", "page_size==100"]
- ["api", "v1/search"] with body={"query": "page title"}
- ["pages", "get", "<page-id>", "--json"]
- ["pages", "create", "--parent", "page:<approved-id>", "--content", "# Title"]
- ["datasources", "query", "<data-source-id>", "--filter", "<literal-json>"]

Use a template path for --spec/--docs and select -X when several methods exist:
["api", "v1/blocks/{block_id}", "-X", "PATCH", "--spec"].
Use a real ID for the actual request. The installed CLI help is the flag authority.

## Writes and scope

Block/page/database/data-source targets and creation parents must be in the
profile's approved roots. Creation without a parent is refused.
Raw comment writes from Notion turns are refused; the gateway owns receipt/reply delivery.
Connection sharing and capabilities still control what Notion permits.

Use a modern database's data_sources list before creating rows. Read schema first.
A page-selection edit should PATCH its exact block, preserving unrelated rich text.
pages edit replaces whole-page Markdown and must not be used for a selected substring.

DELETE/trash/archive needs an exact original-human approve-delete directive for
the target. A model flag, quote or negative sentence does not authorize deletion.
Workers, authentication and paid deployment remain separate operator actions.

## Recovery and verification

Follow has_more and next_cursor. NTN files list returns only its first page.
The tool reports truncation above 60000 output characters. Refine or paginate the read.
Read back every write. Successful mutation responses are cached per triggering comment.
An ambiguous mutation records its intent and is never automatically executed again.
Further mutations for that triggering comment are refused, even if arguments change.
A fresh human request is necessary after checking whether the prior change happened.

NTN uses current official endpoint versions. Gateway baseline reads stay separate;
comment PATCH and modern container fallback use 2026-03-11.
Official documentation: https://developers.notion.com/guides/cli
Use endpoint --docs to retrieve the current official guidance.
