# Program review style guide

Applies to every deck built from `Program_Review_Template.pptx`. Devin follows this file; it does not
invent a style.

## Typeface

| Use | Font | Size | Weight |
| --- | --- | --- | --- |
| Slide title | Calibri | 30 pt | Bold |
| Eyebrow (section label above the title) | Calibri | 12 pt | Bold, all caps, accent blue |
| Body and bullets | Calibri | 17 pt | Regular |
| Table header | Calibri | 13 pt | Bold |
| Table body | Calibri | 12 pt | Regular |
| Speaker notes | Calibri | 11 pt | Regular |

Title slide: 40 pt bold title, 18 pt gray subtitle.

## Palette

| Name | Hex | Use |
| --- | --- | --- |
| Navy | `0B2A4A` | Titles, the bar on the title slide |
| Accent blue | `1F6FB2` | Eyebrows, table header fill, rule lines |
| Ink | `22262B` | Body text |
| Gray | `5A626B` | Subtitles, secondary text |
| Paper | `FFFFFF` | Background — never a colored slide background |

Red is reserved for a risk rated high. Do not use it for emphasis anywhere else.

## Spacing

- Slide size 13.333 × 7.5 in (16:9).
- Left and right margin 0.9 in. Nothing crosses it, including tables.
- Eyebrow at 0.5 in from the top, title at 0.95 in, content starts at 2.0 in.
- 12 pt after each bullet, 6 pt after each line inside a bullet.
- Tables: full content width, header row filled accent blue with white text, 0.4 in rows.

## Slide rules

1. No slide carries more than six lines of text. Detail goes into the speaker notes.
2. Every number on a slide is traceable: the speaker notes name the source file and sheet.
3. One idea per slide. A heading with nothing under it is a bug.
4. Dates are ISO (`2026-09-24`). Schedule variance is in working days.
5. Owners are "First-initial. Lastname" (`A. Reyes`).
6. Titles are a sentence a reviewer could repeat, not a label ("Build 4.1 shipped; the harness
   supplier is now the critical path", not "Status").

## Logo rules

- Program mark bottom-left, 0.9 in from the left edge, 0.4 in from the bottom, 0.32 in tall.
- Customer mark, when one is required, bottom-right on the same baseline.
- Never on a colored fill, never stretched, never recolored.

## Section order

Fixed, and it does not change between cycles:

1. Title
2. Status summary
3. Schedule
4. Risks
5. Decisions needed
