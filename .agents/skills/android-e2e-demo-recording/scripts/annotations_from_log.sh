#!/usr/bin/env bash
# Derive one annotation window per test from the instrumentation log, AFTER the
# run. Racing the run with sleep loops mis-attributes journeys; timestamps do not.
#
# Usage: annotations_from_log.sh [--log /tmp/journeys.log] [--epoch-file <file>]
# Output: <class> <method> <start-offset-s> <end-offset-s>.
# Offsets are relative to the epoch in --epoch-file, which defaults to the RUN
# start (/tmp/demo_run_start_epoch). For offsets that line up with the video,
# write the recorder's start time (`date +%s > /tmp/recording_start_epoch`) when
# you start recording and pass --epoch-file /tmp/recording_start_epoch.
set -euo pipefail

LOG=/tmp/journeys.log
EPOCH_FILE=/tmp/demo_run_start_epoch
while [ $# -gt 0 ]; do
    case "$1" in
        --log) LOG="$2"; shift 2 ;;
        --epoch-file) EPOCH_FILE="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

[ -f "$LOG" ] || { echo "$LOG missing: start the logcat watcher before the run" >&2; exit 1; }
BASE=$(cat "$EPOCH_FILE" 2>/dev/null || awk 'NR==1{print int($1)}' "$LOG")

# adb logcat -v epoch lines look like:
#   1756061234.123  1234  1240 I TestRunner: started: aTest(com.example.BarTest)
# Normalise to "<epoch> <started|finished> <class> <method>" first; mawk has no
# three argument match(), so the parsing lives in sed.
sed -nE 's/^[[:space:]]*([0-9]+)\.[0-9]+.*(started|finished): *[0-9]*:? *([A-Za-z_0-9]+)\(([A-Za-z0-9_.]+)\).*/\1 \2 \4 \3/p' "$LOG" |
awk -v base="$BASE" '
    { key = $3 "\t" $4
      if ($2 == "started") { if (!(key in start)) { start[key] = $1 - base; order[++n] = key } }
      else { end[key] = $1 - base } }
    END { for (i = 1; i <= n; i++) { k = order[i]
              printf "%s\t%s\t%s\n", k, start[k], (k in end ? end[k] : "?") } }
'

cat >&2 <<'EOF'

One annotation window per test above. Two ways to use them:

- ffmpeg drawtext overlay (default): these offsets are post hoc, so burning the
  test name into the video is the only way to label tests shorter than ~10s.
- annotate_recording: it can only stamp the current moment of a LIVE recording,
  so it works only when demoPauseMs makes each test long enough (~10s+) to call
  it in time. Then emit one test_start plus one grouped assertion per test: the
  run reports as many tests as you annotate, so phase level markers show up as
  "2 tests passed".

Execution order is not source order, always read it from this log.
EOF
