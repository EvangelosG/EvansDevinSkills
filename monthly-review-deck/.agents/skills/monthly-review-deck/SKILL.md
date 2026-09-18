---
name: monthly-review-deck
description: Build the monthly program review deck as an editable .pptx from the template, the style guide, this cycle's data and last cycle's deck, then render it and self-check every slide. Use when asked for the program review deck for a month, or to rebuild or correct one.
---

# The monthly program review deck

One argument: the month, as `YYYY-MM` (`/monthly-review-deck 2026-10`). If it is missing, ask for it
before doing anything else — do not guess from today's date.

The format was decided once. Your job is to put this cycle's content into it, not to redesign it.

## Read these first, in this order

All paths are relative to this folder's root (the folder that contains `.agents/`, `template/`,
`data/`, `last-cycle/` and `notes/`).

| File | What you take from it |
| --- | --- |
| `template/Program_Review_Template.pptx` | The masters, layouts and placeholder slides. Start from this file. |
| `template/Style_Guide.md` | Fonts, palette, spacing, slide rules, logo rules, section order. Binding. |
| `data/Schedule_Status_<month>.xlsx` | Every schedule number. Sheets: `Schedule Status`, `Milestones`. |
| `data/Risk_Register_<month>.xlsx` | Every risk. Sheet: `Risk Register`. |
| `last-cycle/Program_Review_<previous month>.pptx` | The running order, the section names, and the shape leadership already reads. |
| `notes/Talking_Points.md` | The angle for this cycle: what to lead with, how to frame it, what not to raise. Rewritten every month by the presenter. |

If a data file for the month is missing, stop and say which one. Never carry last cycle's numbers
forward, and never recall a number from memory.

## What to build

Section order is fixed by the style guide: title, status summary, schedule, risks, decisions needed.

- **Title** — "Program Review — <Month Year>", program name, presenter from last cycle's title slide.
- **Status summary** — a title a reviewer could repeat, then at most four lines. Lead with whatever
  `notes/Talking_Points.md` says to lead with; the ask goes on this slide, not at the end.
- **Schedule** — table of the five tasks with the largest slip, sorted by variance descending:
  task ID, task, baseline finish, forecast finish, variance in working days, owner.
- **Risks** — table of open risks rated high, newest first (by `Opened`): risk ID, risk, owner,
  mitigation due. Risks with status `Closed` never appear.
- **Decisions needed** — one line per decision: what, who owns it, the date it is needed. Take these
  from the asks in `notes/Talking_Points.md` and check each one against the risk register.

Rules that are not negotiable, from `template/Style_Guide.md`: six lines maximum on any slide, detail
moves to the speaker notes, dates are ISO, and every slide carrying numbers names its source file and
sheet in the speaker notes (`Source: data/Risk_Register_2026-09.xlsx, sheet "Risk Register"`).

Save as `Program_Review_<month>.pptx` in the folder root. Real text boxes and real tables, so every
word stays editable in PowerPoint — never an image of a slide, never a PDF export renamed.

## Then check your own work

```bash
soffice --headless --convert-to pdf --outdir . Program_Review_<month>.pptx
```

Look at every page of that PDF and fix what you find, then render and look again:

- text that overflows its box or crosses the 0.9 in margin,
- a heading with nothing under it,
- a table wider than the content area, or rows that spill off the slide,
- low contrast text, or a color outside the palette,
- more than six lines on a slide,
- any number that does not appear in a file under `data/`.

Do not report a deck you have not looked at after the last fix.

## Finish with the three questions

End your message with the three things a reviewer will ask about this deck — the weak spot in the
schedule story, the risk whose mitigation date is closest, and whatever `notes/Talking_Points.md`
told you to avoid raising but the data still shows. One sentence each.

## Next cycle

Drop the new `data/` files in, rewrite `notes/Talking_Points.md`, move last cycle's deck into
`last-cycle/`, and run `/monthly-review-deck <month>`. If a formatting rule changes, change it in
`template/Style_Guide.md` — not here, and not in the deck.
