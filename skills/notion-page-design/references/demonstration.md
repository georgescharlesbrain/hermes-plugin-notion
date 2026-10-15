# Demonstration: a small decision page

Original illustrative content, not a real project update. This is a layout brief;
create native blocks using `notion:use`, not a special Markdown dialect.
Do not create a live page just because this example exists.

## Block plan

1. Page title: "Office handbook review".
2. Plain paragraph: "Decide which handbook changes are ready for publication."
3. Optional gray callout: "Draft for review. Publication is not approved."
4. Heading 2: "Recommendation".
5. Paragraph: "Review the changed sections before choosing a publication date."
6. Heading 2: "Review checklist".
7. Table with a native header row:

   | Section | Check | Status |
   | --- | --- | --- |
   | Arrival | Verify the access instructions | Needs review |
   | Equipment | Confirm the support contact | Needs review |

8. Heading 2: "Next action".
9. Plain paragraph: "Ask the handbook owner to resolve the review items."
10. Optional toggle: "Background notes", containing only supplementary context.

Keep the recommendation, publication warning and next action visible, never inside the
toggle. No image banner, colored heading bars or column layout is needed for this page.
If comparing two independent options later, two short columns may be appropriate;
read the first option then the second to confirm that stacked order still works.

## Readback checklist

- Title, purpose, recommendation, both checklist rows and next action are present.
- The table has a real header row; status is expressed in words, not just color.
- Existing links, code, children and properties remain unchanged on a formatting pass.
- Readback is not a visual preview: inspect a rendered page if available, otherwise
  report the desktop/mobile visual check as pending rather than claiming it passed.
