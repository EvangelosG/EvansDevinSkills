#!/usr/bin/env bash
# Rasterise a .pptx to one PNG per slide so the agent can look at the deck it built.
#
#   scripts/render_deck.sh /tmp/q3-review.pptx [outdir]
#
# Needs LibreOffice (`soffice`). Slides land in outdir (default /tmp/deck-render)
# as slide-1.png, slide-2.png, ...
set -euo pipefail

DECK="${1:?usage: render_deck.sh <deck.pptx> [outdir]}"
OUTDIR="${2:-/tmp/deck-render}"

if ! command -v soffice >/dev/null 2>&1; then
  echo "soffice not found. Install LibreOffice Impress:" >&2
  echo "  macOS:  brew install --cask libreoffice" >&2
  echo "  Debian: sudo apt-get install -y libreoffice-impress" >&2
  echo "  Windows: winget install TheDocumentFoundation.LibreOffice" >&2
  exit 127
fi

rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"

# One PDF, then one PNG per page: soffice's direct pptx->png only emits slide 1.
soffice --headless --convert-to pdf --outdir "$OUTDIR" "$DECK" >/dev/null 2>&1
PDF="$OUTDIR/$(basename "${DECK%.*}").pdf"
[ -f "$PDF" ] || { echo "LibreOffice produced no PDF for $DECK" >&2; exit 1; }

if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -png -r 110 "$PDF" "$OUTDIR/slide"
  # pdftoppm zero-pads (slide-01.png); normalise so slide-1.png always exists.
  for f in "$OUTDIR"/slide-0*.png; do
    [ -e "$f" ] || break
    n=$(basename "$f" .png | sed 's/^slide-0*//')
    [ "$f" = "$OUTDIR/slide-$n.png" ] || mv "$f" "$OUTDIR/slide-$n.png"
  done
else
  echo "pdftoppm not found (apt-get install -y poppler-utils); leaving $PDF" >&2
  exit 127
fi

COUNT=$(find "$OUTDIR" -name 'slide-*.png' | wc -l | tr -d ' ')
echo "rendered $COUNT slide(s) to $OUTDIR"
