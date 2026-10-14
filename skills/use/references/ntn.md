# Profile-scoped ntn commands

The ntn client is the workspace interface. The plugin's automated comment
gateway still uses its own REST client. Do not confuse these paths.

Use terminal to run scripts/ntn_profile.py with Hermes' own Python.
The wrapper accepts api, pages, datasources and files commands.
It uses the active HERMES_HOME; it does not select another profile for you.
Inspect the profile identity before workspace work:

```text
<hermes-python> <plugin-dir>/skills/use/scripts/ntn_profile.py api v1/users/me
```

Read-only examples, with the same wrapper prefix:

```text
api v1/pages/<page-id>
api v1/blocks/<block-id>/children page_size==100
api v1/comments block_id==<block-id> page_size==100
api v1/search query="page title"
pages get <page-id> --json
```

Use api <endpoint> --spec or --docs before an unfamiliar request.
The installed CLI help is the authority for flags.
GET is the default. Body input selects POST unless -X overrides it.
Use name==value for query parameters, path=value for body strings,
and path:=json for typed body values. Use exactly one body source.
The supported JSON-file flag is --data @body.json, not an assumed --json flag.

Follow has_more and next_cursor for complete listings. Do not report the first
page as a complete inventory. Respect rate limits and Retry-After.
A search miss does not prove that a page does not exist.

For authorized writes, retrieve the target first, then use the current schema.
Use the data_source_id for modern database-row parents where required.
Do not copy an old database_id recipe into a newer API without checking it.
Read back every write. Do not automatically repeat a possibly successful write.

CLI Markdown endpoints may use a different API version from the plugin's
2022-06-28 REST client. Do not change the gateway version to match a CLI example.
Use --notion-version only after checking endpoint compatibility.

The wrapper is credential isolation, not a universal mutation-policy sandbox.
Outside automated comment turns, a terminal session retains its own rights.
Human authorization, page sharing and root boundaries still apply.

Official documentation: https://developers.notion.com/guides/cli
Use ntn api <endpoint> --docs for endpoint-specific official guidance.
