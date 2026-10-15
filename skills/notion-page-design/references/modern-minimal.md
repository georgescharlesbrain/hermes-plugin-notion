# Modern Minimal: editorial decisions

These are original recommendations for this plugin, informed by the sources below.
They are not copied templates or a promise that external integration syntax works.

## Default composition

- Leave page-title icons blank: no page-level emoji, image icon or thumbnail. This
  preference concerns the page's icon property, not callout icons or other content.
- Start with the title and a short purpose/takeaway. Add owner/status only when known
  and useful. A gray orientation callout is optional, not a mandatory hero block.
- Use native heading blocks as the navigation spine. Group paragraphs and lists under
  descriptive headings; let ordinary block spacing do the work.
- Keep ordinary text uncolored. Reserve sparse blue emphasis for a meaningful cue and
  labeled red text for a real warning. Default to no accent if it adds no information.
- Place summary, decisions, risks and next steps in the main reading flow. Supplementary
  evidence can go into a clearly labeled toggle after its visible conclusion.
- Favor one column. Two concise, independent comparisons can share a row if they still
  make sense left-column-first when stacked. Do not split a procedure between columns.
- Use real tables with header rows (and header columns where appropriate), not aligned
  spaces or screenshots. Label statuses in words, with color as optional reinforcement.
- Keep headings, labels and substantive content in text. Images support the text; give
  meaningful media a description and a text equivalent for essential information.
- Preserve original content and block relationships. Formatting is not permission to
  summarize away details, change conclusions, move pages or replace unsupported blocks.

## Choosing among conflicting advice

BINER contributes useful attention to page orientation, parallel comparisons, content
preservation and deliberate pattern selection. Its callout-as-heading default and
integration-specific replacement workflow are deliberately not adopted here.
Notion Mastery's Modern Minimal palette contributes neutral surfaces and sparse accents.
Its toggle-first examples are not a rule: essential information stays visible here.
Both sources show enhanced Markdown examples; use the current plugin's technical
instructions and endpoint schemas instead of translating those examples literally.
Rendering claims in those sources concern their toolchains, not all native Notion blocks.
Use simple composition and test the actual renderer rather than treating them as API law.

## Sources

- [BINER notion-beautifier](https://github.com/Percona-Lab/BINER/blob/HEAD/skills/notion-beautifier/SKILL.md):
  reviewed for preservation, orientation and purposeful use of layout patterns.
- [Notion Mastery: page design patterns](https://github.com/thelobbi/claude-m/blob/main/notion/skills/notion-mastery/references/page-design-patterns.md):
  reviewed especially for Modern Minimal and mobile stacking considerations.

Original synthesis; no source text, code or template is redistributed. Consult upstream
licenses before reusing their material. These mutable source links document inspiration,
not a dependency or an instruction to fetch and execute upstream content.
