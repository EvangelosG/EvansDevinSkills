# Talk track — Building a PowerPoint skill in Devin Desktop

~55 minutes: 35 talking and demoing, 15 hands-on, 5 spare. Slide numbers match
`deck.yaml`. Everything in *italics* is stage direction, not a script to read out.

Build the deck with:

```
python3 ../../.agents/skills/quarterly-deck/scripts/build_deck.py deck.yaml \
    --brand brand.yaml --out /tmp/workshop.pptx
```

---

## 1. Building a PowerPoint skill (1 min)

Open by naming the thing they already do: somebody on their team rebuilds the same
deck every month. We are not going to make Devin write a deck — a chatbot can do
that. We are going to write down *how their deck gets made*, once, and then run it.

*Have the finished Q3 deck open in another window. Do not show it yet.*

## 2. Where this lands (2 min)

Their own words were metrics capture, PowerPoint decks, admin tasks. That trio is
almost always one loop: pull numbers, paste into last quarter's file, reformat.

Ask the room directly: **which deck do you rebuild most often?** Write the answer
down — you will use it in the hands-on segment. If they name something you did not
expect, say so and adapt; the demo does not depend on being right.

## 3. A prompt is a session. A skill is a process. (3 min)

The honest version of the pitch: a good prompt gets you a good deck once. The next
person writes their own prompt, gets a different deck, and neither of them is your
template.

A skill is a file in the repo. It is reviewed like code, it is shared, it carries
the things a model cannot guess — which layout is the section header, how many
bullets your brand team tolerates, where the footer goes.

## 4. What you have open (2 min)

Housekeeping, briefly, because some of them will have read older docs: Desktop
v3.9.19 removed Cascade. Devin Local is the agent now, it uses the same skill
format as the CLI and cloud Devin, and Memories and Workflows are gone — skills
replace both. Anyone with old Cascade conversations can run **Devin: Open Cascade
Migration Wizard**.

## 5. Anatomy of a skill (section divider)

*No notes. Move through it.*

## 6. A skill is a folder (3 min)

`SKILL.md` plus whatever it needs. For a deck skill, "whatever it needs" is the
important half: your `.pptx` template, a generator script, the brand rules.

Project skills live in `.agents/skills/<name>/` and get committed — that is the
version that matters, because it is the team's. Global skills live in
`~/.config/devin/skills/`, or `%APPDATA%\devin\skills\` on Windows; those are just
yours.

## 7. The frontmatter (2 min)

Only two fields are required. Do not let anyone spend the workshop tuning
`allowed-tools`.

## 8. The description is the trigger (3 min)

This is the slide to slow down on. Devin only keeps the name and description in
context; it reads the rest when it decides the skill applies. So the description is
not documentation, it is the trigger — write *when to use this*, not *what this is*.

Read both examples off the slide out loud. The difference between them is the
difference between a skill that fires and one that sits there.

## 9. Let's build one (section divider)

*Switch to Devin Desktop. Full screen. Font size up.*

## 10. Live — ask Devin Local to author the skill (6 min)

There is no "new skill" button — you build it by talking. Type roughly:

> Create a skill called quarterly-deck. It should turn a metrics CSV and a page of
> rough notes into an on-brand quarterly review deck: read the sources, propose an
> outline, wait for me to approve it, build the .pptx, validate it against our brand
> rules, then render the slides and look at them.

While it works, narrate what you asked for and — more importantly — what you did
*not* ask for: you never said python-pptx, or how to check the deck. Then open the
`SKILL.md` it wrote and read the description together.

**Change one thing live.** Anything: make it four bullets, add "never use red".
Editing the file in front of them is the moment the abstraction becomes concrete.

*Then show the customizations panel so they can see the skill loaded.*

## 11. Live — run it (5 min)

`/quarterly-deck Q3 FY26`, or just describe the task and let the description do its
job — worth doing it that way once so they see automatic invocation.

It reads `metrics.csv` and `notes.md`, then comes back with an outline. **Stop
here.** This is the checkpoint that makes the whole thing safe: you are arguing
about the outline while it is cheap, not about a finished 30-slide deck. Reject one
slide on purpose.

## 12. The step that earns trust (4 min)

*Show the checker output, then the rendered PNGs.*

The deck is validated — bullet counts, title length, missing source notes, and text
estimated to overflow its box — and then rendered to images and looked at. Overflow
is the classic PowerPoint failure and it is invisible in the file; only a picture
catches it.

Say the quiet part: the checker cannot tell you whether the deck says anything
worth saying. That is still the human's job, and it is the job worth keeping.

## 13. Live — change your mind (4 min)

Two edits, both fast. Set `max_bullets_per_slide: 4` in `brand.yaml`, rerun the
checker, watch the summary slide fail, let Devin shorten it. Then add a risks slide
to the spec and rebuild.

Land the line: **the deck is disposable, the skill is the asset.**

## 14. Making it yours (3 min)

Everything so far used a stand-in template. Drop in their real `.pptx` and the deck
inherits their master slides — that is the single biggest jump in output quality
and it costs nothing.

Their layouts will be in a different order, so the skill has a script that prints
the layout indices; you re-map once and never think about it again. Same for brand
rules: put their real limits in `brand.yaml` and the checker enforces their brand.

## 15. Your turn — 15 minutes (15 min)

Pairs. Each pair picks one deck they actually rebuild, asks Devin Local to write the
skill, reads what it wrote, runs it on fake numbers, then fixes one thing they did
not like.

*Walk the room. The two failure modes to look for: a vague description that never
triggers, and a skill that describes the deck instead of the procedure for making
it.*

Close on committing it — a skill in someone's home directory helps one person; a
skill in the repo is how the team stops rebuilding the same deck.

---

## Appendix — what you need on your own machine

Not worth live time; mention it exists and move on.

- Devin Desktop v3.9.19 or later
- Python 3 with `python-pptx`, `PyYAML`, `Pillow`
- LibreOffice (`soffice`) and poppler-utils (`pdftoppm`) to render slides to images
- Without the last two, the skill still builds and validates decks — it just cannot
  show you a picture, and it will say so rather than pretend

If their laptops are locked down, this is the part that will bite them; it is a
their-IT conversation, not a Devin one.

## Appendix — if the live demo breaks

- Devin picks the wrong layout → open `deckkit.py`, show `LAYOUTS`, fix the index.
  This is a good failure to have in public; it is exactly what the skill is for.
- The checker fails on something you did not plan → read it out loud and fix it.
  A validator that never fires looks fake anyway.
- Rendering is slow or unavailable → open the `.pptx` in PowerPoint instead.
- Everything is on fire → the built deck is in the repo; open it and keep talking.
