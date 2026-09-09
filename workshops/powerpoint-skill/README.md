# Workshop — building a PowerPoint skill in Devin Desktop

A ~55 minute session that teaches a client to write and run a deck-generating skill
in **Devin Local** (Devin Desktop v3.9.19 removed Cascade).

| File | What it is |
| --- | --- |
| [`talk-track.md`](talk-track.md) | Speaker notes, timings, the exact prompts to type live, and a break-glass appendix |
| [`deck.yaml`](deck.yaml) | The slides |
| [`brand.yaml`](brand.yaml) | Colours, fonts, and the rules the checker enforces for this deck |

The deck is built by the skill it teaches — [`quarterly-deck`](../../.agents/skills/quarterly-deck/):

```bash
S=../../.agents/skills/quarterly-deck/scripts
python3 $S/build_deck.py deck.yaml --brand brand.yaml --out /tmp/workshop.pptx
python3 $S/check_deck.py /tmp/workshop.pptx --brand brand.yaml
$S/render_deck.sh /tmp/workshop.pptx /tmp/workshop-render
```

The live demo runs the same skill against its own sample data in
[`.agents/skills/quarterly-deck/example/`](../../.agents/skills/quarterly-deck/example/) —
a fictional logistics company, so nothing depends on the client's systems or files.
