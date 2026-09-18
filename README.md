# Evan's Devin skills

Shared [Devin skills](https://docs.devin.ai). Each lives in `.agents/skills/<name>/` with a `SKILL.md`
that Devin reads, plus whatever scripts it needs.

| Skill | What it does |
| --- | --- |
| [`android-e2e-demo-recording`](.agents/skills/android-e2e-demo-recording/) | Runs an Android app's unit + instrumented (Compose) tests on a Devin box and records one continuous side-by-side demo video of them, with each test's name burned in from the device log. |
| [`monthly-review-deck`](.agents/skills/monthly-review-deck/) | Builds a recurring program review deck as an editable `.pptx` from an approved template and style guide, this cycle's data and last cycle's deck, then renders it and reviews its own slides. |

## Installing one

Once, by hand: copy the skill's directory into the target repo's `.agents/skills/`, commit it, and edit
the values it calls out (for `android-e2e-demo-recording`, the five in its `config.env`). From then on
it is that repo's skill and Devin picks it up on its own — nothing here is fetched at run time.

Each `SKILL.md` therefore documents only how to *use* the skill, not how to install it.

For a robust list of Android specific skills, see https://github.com/android/skills

## Examples

| Example | What it is for |
| --- | --- |
| [`examples/monthly-review-deck`](examples/monthly-review-deck/) | Input folder for demoing "a recurring deck as a Skill" live: an approved template and style guide, this cycle's data, last cycle's deck, and the presenter's talking points. Fictional data. |

Open the example folder itself in Devin Desktop (`File → Open Folder → examples/monthly-review-deck/`),
since the skill's paths are relative to the folder that holds `template/`, `data/`, `last-cycle/` and
`notes/`.

It deliberately ships without the skill, so a demo can build the deck by hand first and then ask Devin
to write the skill — which is the point of the exercise. To skip that and run it straight away, copy
[`.agents/skills/monthly-review-deck/`](.agents/skills/monthly-review-deck/) into the example folder
and run `/monthly-review-deck 2026-09`:

```bash
mkdir -p examples/monthly-review-deck/.agents/skills
cp -r .agents/skills/monthly-review-deck examples/monthly-review-deck/.agents/skills/
```
