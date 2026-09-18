# Evan's Devin skills

Shared [Devin skills](https://docs.devin.ai). Each lives in `.agents/skills/<name>/` with a `SKILL.md`
that Devin reads, plus whatever scripts it needs.

| Skill | What it does |
| --- | --- |
| [`android-e2e-demo-recording`](.agents/skills/android-e2e-demo-recording/) | Runs an Android app's unit + instrumented (Compose) tests on a Devin box and records one continuous side-by-side demo video of them, with each test's name burned in from the device log. |
| [`monthly-review-deck`](.agents/skills/monthly-review-deck/) | Builds the monthly program review deck as an editable .pptx from the template, style guide, this cycle's workbooks and last cycle's deck, renders it, and checks every slide. Ships with the working folder it reads. |

## Installing one

Once, by hand: copy the skill's directory into the target repo's `.agents/skills/`, commit it, and edit
the values it calls out (for `android-e2e-demo-recording`, the five in its `config.env`). From then on
it is that repo's skill and Devin picks it up on its own — nothing here is fetched at run time.

Each `SKILL.md` therefore documents only how to *use* the skill, not how to install it.

For a robust list of Android specific skills, see https://github.com/android/skills

## [`monthly-review-deck`](.agents/skills/monthly-review-deck/)

This one carries its inputs with it — a program manager's whole working folder lives inside the
skill, so copying the directory copies everything it reads:

```text
.agents/skills/monthly-review-deck/
├── SKILL.md                               the procedure, written once
├── template/
│   ├── Program_Review_Template.pptx       approved master slides
│   └── Style_Guide.md                     fonts, palette, spacing, logo rules
├── data/
│   ├── Schedule_Status_2026-09.xlsx       this cycle
│   └── Risk_Register_2026-09.xlsx
├── last-cycle/
│   └── Program_Review_2026-08.pptx        the shape leadership expects
└── notes/
    └── Talking_Points.md                  you rewrite this each cycle
```

Open this repo in Devin Desktop and run `/monthly-review-deck 2026-09`; the deck lands next to
`SKILL.md`. Next cycle: drop the new `data/` files in, rewrite `notes/Talking_Points.md`, move the
deck you just made into `last-cycle/`, run it again.

The data is fictional.
