---
name: quarterly-deck
description: Turn a metrics CSV plus rough notes into an on-brand quarterly review PowerPoint deck, then validate and render it. Use when asked to build, update, or check a quarterly/monthly business review deck, a QBR, or any .pptx built from metrics and notes.
argument-hint: "<quarter, e.g. Q3 FY26>"
---

# Quarterly review deck

Numbers and notes in, a checked `.pptx` out. The deck is generated from a spec you
review first, so the argument the humans have is about the outline, not about
fixing fonts afterwards.

## Procedure

1. **Read the sources.** Metrics live in CSVs; the story lives in someone's notes.
   `example/` has both, and is a working sample you can copy.
2. **Write a deck spec** — a YAML file listing slides in order. Start from
   `example/deck.yaml`; the slide types are below.
3. **Show the spec to the user and wait.** The outline is cheap to change and the
   deck is not. Do not build until they have agreed to it.
4. **Build:** `python3 scripts/build_deck.py <spec>.yaml --out <deck>.pptx`
   (`--brand` and `--template` override the skill's own, for a second brand.)
5. **Check:** `python3 scripts/check_deck.py <deck>.pptx` — exits non-zero and
   names the slide on any brand violation. Fix the spec, rebuild, re-check.
6. **Look at it:** `scripts/render_deck.sh <deck>.pptx` writes one PNG per slide to
   `/tmp/deck-render`. Open them. The checker catches mechanical faults; only your
   eyes catch a chart that misleads or a slide that says nothing.

Never hand over a deck that has not been through steps 5 and 6.

## Slide types

Every slide is one list item under `slides:` with a `type` and a `title`.

| `type` | Other keys |
| --- | --- |
| `title` | `subtitle`, `presenter`, `date` |
| `bullets` | `bullets` (list) |
| `two_column` | `left_heading`, `left_bullets`, `right_heading`, `right_bullets` |
| `table` | `source` (CSV, relative to the spec), `source_note` |
| `chart` | `source`, `category_column`, `series_columns` (list), `chart_type` (`line`/`column`/`bar`), `source_note` |
| `section` | `text` |
| `closing` | `bullets` |

Charts are native PowerPoint charts, not images: the client can click into them
and edit the numbers.

## Brand

`brand.yaml` holds the colours, fonts, footer, and the rules `check_deck.py`
enforces (bullets per slide, characters per bullet, title length, whether data
slides need a source note). Change the rules there rather than arguing with the
checker.

## Using a real corporate template

`template.pptx` is a stand-in generated from `brand.yaml`
(`python3 scripts/make_template.py`). Replace it with the client's own `.pptx` and
the deck inherits their master slides. Their layouts will be in a different order,
so afterwards:

```
python3 scripts/inspect_template.py    # prints layout indices and placeholders
```

and update `LAYOUTS` in `scripts/deckkit.py` to match. Also update the colours and
fonts in `brand.yaml` so the checker enforces their brand rather than this one.

## Requirements

Python 3 with `python-pptx`, `PyYAML`, and `Pillow`. Rendering needs LibreOffice
(`soffice`) and `pdftoppm` from poppler-utils; without them, skip step 6 and say so
rather than pretending the deck was inspected.

## Tests

`python3 -m pytest tests` from the skill directory covers the spec parsing, the
builder, and every rule in the checker.
