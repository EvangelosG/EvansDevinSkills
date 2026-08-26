#!/usr/bin/env bash
# Place the emulator and a konsole side by side, filling the desktop.
# Geometry is derived from the actual display size, never hard coded.
# Usage: place_windows.sh [workdir]
set -euo pipefail

# shellcheck source=_config.sh
. "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
WORKDIR="${1:-$REPO_ROOT}"
export DISPLAY="${DISPLAY:-:0}"

EMU_RE='Android Emulator - '
TERM_RE='Konsole'
TOP=28          # below the panel
BOTTOM_PAD=52   # above the panel
SIDE_PAD=8
TOOLBAR_PAD=70  # the emulator's floating side toolbar is a separate window

read -r SCREEN_W SCREEN_H < <(xdotool getdisplaygeometry)
USABLE_H=$((SCREEN_H - TOP - BOTTOM_PAD))

win_geom() { # <regex> -> "id x y w h" of the first matching window
    wmctrl -lG | grep -E "$1" | head -1 | awk '{print $1, $3, $4, $5, $6}'
}

wait_for_window() { # <regex> <seconds>
    local re="$1" deadline=$((SECONDS + ${2:-30}))
    until [ -n "$(win_geom "$re")" ]; do
        [ "$SECONDS" -ge "$deadline" ] && { echo "no window matching /$re/ after ${2}s" >&2; return 1; }
        sleep 1
    done
}

wait_for_window "$EMU_RE" 30

if [ -z "$(win_geom "$TERM_RE")" ]; then
    setsid konsole --workdir "$WORKDIR" >/dev/null 2>&1 < /dev/null &
    wait_for_window "$TERM_RE" 30
fi

# Close only known noise. Do not sweep every other window: the emulator's own
# side toolbar is a separate top level window named "Emulator", and closing it
# closes the device.
# grep exits 1 when the box happens to have none of them open, which pipefail
# would turn into an abort before anything is placed.
wmctrl -l | { grep -E 'Chrome|Nested Virtualization|Firefox' || true; } | awk '{print $1}' | while read -r id; do
    wmctrl -i -c "$id" || true
done

# The emulator keeps the device aspect ratio: it will shrink the requested width
# to whatever matches the height, so ask for full height and measure the result.
read -r EMU_ID _ _ _ _ < <(win_geom "$EMU_RE")
wmctrl -i -r "$EMU_ID" -e "0,$SIDE_PAD,$TOP,$((SCREEN_W / 2)),$USABLE_H"
sleep 2
read -r _ EMU_X _ EMU_W _ < <(win_geom "$EMU_RE")

TERM_X=$((EMU_X + EMU_W + TOOLBAR_PAD))
TERM_W=$((SCREEN_W - TERM_X - SIDE_PAD))
read -r TERM_ID _ _ _ _ < <(win_geom "$TERM_RE")
wmctrl -i -r "$TERM_ID" -e "0,$TERM_X,$TOP,$TERM_W,$USABLE_H"
sleep 1

# label_video.sh keeps its overlay inside this pane instead of across the desktop.
echo "$EMU_X $TOP $EMU_W $USABLE_H" > /tmp/demo_emulator_geometry

echo "display ${SCREEN_W}x${SCREEN_H}; emulator ${EMU_W}px wide at x=${EMU_X}; konsole ${TERM_W}px at x=${TERM_X}"
wmctrl -lG | grep -E "$EMU_RE|$TERM_RE"
echo "Run this inside the konsole to enlarge its font: printf '\\033]50;FontSize=16\\a'; clear"
