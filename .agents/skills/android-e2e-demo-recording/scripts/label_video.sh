#!/usr/bin/env bash
# Draw the name of the running test onto the video, one label per test window.
#
# The names are not written anywhere: they come from annotations_from_log.sh,
# which reads whatever tests the device actually ran. This exists because
# annotate_recording can only mark a LIVE recording at the current moment, so
# tests shorter than ~10s cannot be labelled that way.
#
# Offsets default to /tmp/video_start_epoch (written by finalize_recording.sh
# from the first chunk's creation time). Do not use the run's start epoch here:
# the recorder is already running by the time the run starts, and that gap is
# however long the operator took to type, which drifts the labels by 2-3 tests.
#
# Usage: label_video.sh <in.mp4> <out.mp4> [--trim-head SECONDS] [--epoch-file FILE]
#   --trim-head  seconds cut off the head of <in.mp4> since it was recorded;
#                without it the labels lead the picture by exactly that much.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
IN="${1:?usage: label_video.sh <in.mp4> <out.mp4> [--trim-head S] [--epoch-file FILE]}"
OUT="${2:?usage: label_video.sh <in.mp4> <out.mp4> [--trim-head S] [--epoch-file FILE]}"
shift 2

TRIM_HEAD=0
ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --trim-head) TRIM_HEAD="$2"; shift 2 ;;
        *) ARGS+=("$1"); shift ;;
    esac
done
[ "${#ARGS[@]}" -eq 0 ] && ARGS=(--epoch-file /tmp/video_start_epoch)

ANN=$("$SCRIPT_DIR/annotations_from_log.sh" "${ARGS[@]}" 2>/dev/null)
[ -n "$ANN" ] || { echo "no test windows in the log; nothing to label" >&2; exit 1; }

# Keep the label inside the emulator pane rather than across the whole desktop.
# place_windows.sh records the pane it created; fall back to the left third.
VIDEO_W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$IN")
if [ -f /tmp/demo_emulator_geometry ]; then
    read -r PANE_X _ PANE_W _ < /tmp/demo_emulator_geometry
else
    PANE_X=8; PANE_W=$((VIDEO_W / 3))
fi

FILTER=""
while IFS=$'\t' read -r _class method start end; do
    [ "$end" = "?" ] && continue
    start=$((start - TRIM_HEAD)); end=$((end - TRIM_HEAD))
    [ "$end" -le 0 ] && continue
    [ "$start" -lt 0 ] && start=0
    # Shrink long names so the label never spills into the console pane;
    # drawtext glyphs are roughly 0.55 * fontsize wide.
    FS=$(( (PANE_W - 20) * 100 / (55 * ${#method}) ))
    [ "$FS" -gt 24 ] && FS=24
    [ "$FS" -lt 11 ] && FS=11
    [ -n "$FILTER" ] && FILTER="$FILTER,"
    FILTER="$FILTER drawtext=text='${method//\'/}':x=$((PANE_X + 10)):y=H-60:fontsize=$FS"
    FILTER="$FILTER:fontcolor=white:box=1:boxcolor=black@0.6:enable='between(t,$start,$end)'"
done <<< "$ANN"

ffmpeg -y -i "$IN" -vf "$FILTER" -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p "$OUT"
echo "wrote $OUT ($(wc -l <<< "$ANN") labels)"
