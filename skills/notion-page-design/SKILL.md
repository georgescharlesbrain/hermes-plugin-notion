---
name: notion-page-design
description: Design readable Notion pages with restrained native blocks.
version: 0.1.0
author: Koen (georgescharlesbrain), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [notion, design, accessibility, editorial]
    related_skills: [use]
---

# Notion page design

Design the reading experience, not a decorative wrapper. Default to Modern Minimal:
native text, useful headings, one clear reading path and selective emphasis.
This is editorial guidance; it grants no workspace access or write permission.

## When to use

- Create, format or redesign a Notion page, template, report or reference guide.
- Improve scanability, hierarchy, layout or accessibility without changing meaning.
- Not for wiki governance: load `knowledge-management` for conceptual organization,
  provenance and ownership. Load `notion:use` for technical operations and permissions.
- If a required skill is unavailable or blocked, report the gap; never bypass it.

## Prerequisites

Resolve the actual profile, approved target/parent, reader, purpose and edit scope.
Use `skill_view(name="notion:notion-page-design", file_path="references/modern-minimal.md")`
for design choices and source rationale. Load `references/demonstration.md` for a
small original layout example. Neither reference is an API or Markdown dialect spec.

## Procedure

1. Read the full target and relevant descendants through `notion:use` before editing.
   Inventory text, links, code, tables, child blocks, properties and embeds; flag
   missing or unsupported material before making a change.
2. State the page's purpose and primary takeaway in native text near the top.
   Use the existing title; keep owner, status and next action visible when relevant.
3. Build a native heading hierarchy with descriptive text headings, not image
   banners, bold paragraphs or callouts masquerading as headings. Avoid skipped levels.
4. Prefer a single column. Use at most two columns only for independent parallel
   material; keep instructions, wide tables and code in the main flow. Confirm the
   reading order remains meaningful when columns stack on mobile or linearize.
5. Keep default text colors. Use restrained callouts for a brief orientation or a
   genuine warning, not every section. A neutral gray summary is optional; blue is
   occasional emphasis, red is a labeled warning. Never encode meaning by color alone.
6. Use tables for comparisons and structured facts, with explicit headers and concise
   cells. Use lists for sequences. Keep essential info, decisions, warnings, actions
   and necessary code outside toggles; reserve toggles for supplementary detail.
7. Keep all substantive text searchable and selectable: no image text as a substitute
   for content. Give useful images descriptive captions/alt text where supported,
   with an adjacent text equivalent for any information needed to act.
8. Preserve all original content, facts, links, code, values and child-page relations
   on a formatting-only request. Do not rewrite, drop or replace unsupported blocks.
   Propose meaning changes separately. Prefer targeted block edits over replacement;
   whole-page replacement needs explicit approval under `notion:use`.
9. Apply only the approved changes through the current profile's tools. Use the
   actual tool's documented block schema; never paste another integration's enhanced
   Markdown/XML syntax on the assumption it will render here.
10. Retrieve and read back the exact changed page/blocks and affected descendants.
    Compare the inventory, hierarchy, table headers, links, properties and parent;
    verify no duplicate or missing content. Inspect rendered desktop/narrow layouts
    when available. If only API readback is possible, say visual verification is pending.

## Pitfalls

- Do not copy source templates, mandatory color systems or tool names into this plugin.
- Avoid nested callouts, nested columns, deep toggles and decorative spacer blocks.
- Do not move a page, alter sharing, assign an owner or invent metadata for appearance.
- Do not claim screenshots or API success prove preservation without comparison.

## Verification

Report the exact target, scope changed, preservation checks and unresolved rendering
limits. Success means readable native structure, accessible reading order and verified
content, not merely an accepted write. No live demonstration is required by this skill.
