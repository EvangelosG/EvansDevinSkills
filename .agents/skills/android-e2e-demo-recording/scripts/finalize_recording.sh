#!/usr/bin/env bash
# Turn the screen recorder's raw chunks into ONE 1x mp4 plus a contact sheet.
# Never ship the recorder's own *-edited.mp4: it is time lapsed (200s -> 18s).
#
# Usage: finalize_recording.sh <screencast-dir> [output.mp4]
#   <screencast-dir> is ~/screencasts/<recording-id>/ on a Devin box.
set -euo pipefail

DIR="${1:?usage: finalize_recording.sh <screencast-dir> [output.mp4]}"
OUT="${2:-$PWD/take_1x.mp4}"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac

cd "$DIR"
mapfile -t RAWS < <(ls -- *-raw-*.mkv 2>/dev/null | sort)
[ "${#RAWS[@]}" -gt 0 ] || { echo "no *-raw-*.mkv chunks in $DIR" >&2; exit 1; }

# The chunks are one continuous capture, split only by the recorder.
# ffmpeg resolves concat entries relative to the list file, so use absolute paths.
printf "file '%s'\n" "${RAWS[@]/#/$PWD/}" > "$DIR/raws.txt"
ffmpeg -y -f concat -safe 0 -i "$DIR/raws.txt" \
    -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p "$OUT"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")

# When the video starts, in epoch time. The recorder is already running by the
# time anyone types the first command, so the operator cannot time this by hand;
# label_video.sh needs it to map test timestamps onto video time.
VIDEO_START=$(stat -c %W "${RAWS[0]}")
if [ "${VIDEO_START:-0}" -le 0 ]; then      # no birth time on this filesystem
    FIRST_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${RAWS[0]}")
    VIDEO_START=$(( $(stat -c %Y "${RAWS[0]}") - ${FIRST_DUR%.*} ))
fi
echo "$VIDEO_START" > /tmp/video_start_epoch

# Aim for ~18 tiles whatever the take's length; a fixed 1/12 leaves a short take
# mostly empty.
SHEET="${OUT%.mp4}_sheet.png"
ffmpeg -y -i "$OUT" -vf "fps=18/${DUR%.*},scale=320:-1,tile=6x3" -frames:v 1 "$SHEET"

echo "wrote $OUT (${DUR}s)"
echo "wrote $SHEET  (skim it: every phase of the run should be visible)"
echo "video starts at epoch $VIDEO_START -> /tmp/video_start_epoch"
