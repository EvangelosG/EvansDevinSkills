# Evan's Devin skills

Shared [Devin skills](https://docs.devin.ai). Each lives in `.agents/skills/<name>/` with a `SKILL.md`
that Devin reads, plus whatever scripts it needs.

| Skill | What it does |
| --- | --- |
| [`android-e2e-demo-recording`](.agents/skills/android-e2e-demo-recording/) | Runs an Android app's unit + instrumented (Compose) tests on a Devin box and records one continuous side-by-side demo video of them, with each test's name burned in from the device log. |

## Installing one

Once, by hand: copy the skill's directory into the target repo's `.agents/skills/`, commit it, and edit
the values it calls out (for `android-e2e-demo-recording`, the five in its `config.env`). From then on
it is that repo's skill and Devin picks it up on its own — nothing here is fetched at run time.

Each `SKILL.md` therefore documents only how to *use* the skill, not how to install it.

For a robust list of Android specific skills, see https://github.com/android/skills

## Examples

| Example | What it is for |
| --- | --- |
| [`examples/monthly-review-deck`](examples/monthly-review-deck/) | A self-contained folder for demoing "a recurring deck as a Skill" live: an approved template and style guide, this cycle's data, last cycle's deck, the presenter's talking points, and the `monthly-review-deck` skill that turns them into an editable `.pptx`. |

Open the example folder itself in Devin Desktop (`File → Open Folder → examples/monthly-review-deck/`)
so its own `.agents/skills/` is picked up, then run `/monthly-review-deck 2026-09`. The data is
fictional.
