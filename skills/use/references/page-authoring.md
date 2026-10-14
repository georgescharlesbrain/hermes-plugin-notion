# Page authoring through ntn

This replaces the host's MCP-specific page-authoring skill.
It does not enable page edits from automated comment turns.

1. Retrieve the target page or parent through the current profile.
2. For a database row, retrieve the schema and use its exact data_source_id,
   title-property name and property types.
3. Clarify proposed versus applied edits, the destination and the content source.
4. Check the current ntn pages command help or API --spec before writing.
5. Apply the authorized change without deleting unrelated content.
6. Retrieve the result and verify title, parent, headings and changed text.

An internal connection may create children only under accessible, approved
parents. Do not attempt workspace-root creation as an access workaround.
A manager role alone does not grant child creation or broad page sharing.
Put a page where the human specifies, not where its subject suggests.

For a small edit, preserve existing structure and identify the exact changed
section. Do not replace a whole page to avoid understanding its existing blocks.
For a structural edit, read the full result back.

The ntn pages get output can contain frontmatter and partial Markdown.
Check unknown_block_ids and truncation before using it as a complete source.
Read the current Notion Markdown specification before relying on special tags.
Do not copy old MCP tool names, collection URLs or Markdown assumptions into CLI
API payloads without checking the current endpoint.

If a page becomes a working copy of a decision, identify its source and authority.
A request for plugin filesystem documentation does not authorize publishing it
into the Notion workspace.

Selected-text discussions are created by humans in Notion. The API can reply to
an existing discussion; parent-block context does not prove an exact selection.

Preserved source guidance: Koen/Aroa's page-authoring workflow and the MIT
community Notion skill. Obsolete MCP access instructions are intentionally omitted.
