# Evan's Devin skills

Shared [Devin skills](https://docs.devin.ai). Each lives in `.agents/skills/<name>/` with a `SKILL.md`
that Devin reads, plus whatever scripts it needs.

| Skill | What it does |
| --- | --- |
| [`android-e2e-demo-recording`](.agents/skills/android-e2e-demo-recording/) | Runs an Android app's unit + instrumented (Compose) tests on a Devin box and records one continuous side-by-side demo video of them, with each test's name burned in from the device log. |
| [`quarterly-deck`](.agents/skills/quarterly-deck/) | Turns a metrics CSV and a page of rough notes into an on-brand quarterly review `.pptx`, checks it against the brand rules, and renders every slide to look at. |

## Installing one

Once, by hand: copy the skill's directory into the target repo's `.agents/skills/`, commit it, and edit
the values it calls out (for `android-e2e-demo-recording`, the five in its `config.env`). From then on
it is that repo's skill and Devin picks it up on its own — nothing here is fetched at run time.

Each `SKILL.md` therefore documents only how to *use* the skill, not how to install it.

For a robust list of Android specific skills, see https://github.com/android/skills

## Workshops

[`workshops/powerpoint-skill/`](workshops/powerpoint-skill/) — a client session on writing and running
a deck-generating skill in Devin Local, with speaker notes. Its own slides are built by `quarterly-deck`.
