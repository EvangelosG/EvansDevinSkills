#!/usr/bin/env bash
# Run the demoed suite (unit + :app instrumented) with output filtered for video.
# This is the ONLY thing that should be typed in the on-camera konsole.
#
# Usage: run_demo_suite.sh [--pause-ms N] [--prewarm]
#   --prewarm   build everything and exit; run this BEFORE recording, off camera
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=_config.sh
. "$SCRIPT_DIR/_config.sh"
cd "$REPO_ROOT" || exit 1

PAUSE_MS=0     # pauses cost more video than they buy; opt in per take
read -r -a UNIT_TASK_LIST <<< "$UNIT_TASKS"
JOURNEY_LOG=/tmp/journeys.log

# Each phase starts on a clean screen so the video is readable. `clear` fails when
# TERM is unset (any non-interactive shell), which must not abort the run.
screen_clear() { clear 2>/dev/null || printf '\033c'; }

GRADLE_LOG=/tmp/demo_gradle.log

# Runs Gradle showing only <display-regex> on camera; on failure, restores the
# diagnosis that filter just hid (see explain_gradle_failure).
#   gradle_phase <display-regex> <gradle args...>
gradle_phase() {
    local display_re="$1" status
    shift
    set +e
    # grep -E, never -Ei: a case insensitive BUILD matches every "preBuild UP-TO-DATE"
    # line and floods the screen. || true so a no-match grep does not kill the run.
    ./gradlew "$@" --console=plain 2>&1 | tee "$GRADLE_LOG" | { grep -E "$display_re" || true; }
    status=${PIPESTATUS[0]}
    set -e
    [ "$status" -eq 0 ] && return 0
    explain_gradle_failure "$GRADLE_LOG" "$display_re"
    exit "$status"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --pause-ms) PAUSE_MS="$2"; shift 2 ;;
        --prewarm)
            gradle_phase '.' \
                "$APP_MODULE:assemble$VARIANT" "$APP_MODULE:assemble${VARIANT}AndroidTest" \
                "${UNIT_TASK_LIST[@]}"
            exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# Test names + timestamps for post-run annotation; see annotations_from_log.sh.
adb logcat -c
pkill -f 'adb logcat -s TestRunner' >/dev/null 2>&1 || true
nohup bash -c "adb logcat -v epoch -s TestRunner:I | stdbuf -oL grep -E 'started:|finished:' > $JOURNEY_LOG" >/dev/null 2>&1 &
trap 'pkill -f "adb logcat -s TestRunner" >/dev/null 2>&1 || true' EXIT

date +%s > /tmp/demo_run_start_epoch

# Gradle marks test tasks UP-TO-DATE on a re-run, so --rerun per task.
RERUN_TASKS=()
for t in "${UNIT_TASK_LIST[@]}"; do RERUN_TASKS+=("$t" --rerun); done

screen_clear
gradle_phase 'Task :[A-Za-z0-9:_-]*UnitTest$|BUILD SUCCESSFUL|BUILD FAILED|FAILURE' \
    "${RERUN_TASKS[@]}"

screen_clear
while read -r d; do
    for f in "$d"/*.xml; do
        [ -f "$f" ] || continue
        head -2 "$f" | { grep -o 'name="[^"]*" tests="[0-9]*" skipped="[0-9]*" failures="[0-9]*" errors="[0-9]*"' || true; }
    done
done < <(unit_results_dirs)

screen_clear
# $PAUSE_ARG is read by the app's demo-aware test classes; it defaults to 0 there,
# so CI is unaffected, and it is simply ignored by classes that do not read it.
gradle_phase 'Starting [0-9]+ tests|Tests [0-9]+/|Finished [0-9]+ tests|BUILD SUCCESSFUL|BUILD FAILED|FAILURE|failed' \
    "$CONNECTED_TASK" -Pandroid.testInstrumentationRunnerArguments."$PAUSE_ARG"="$PAUSE_MS"

date +%s > /tmp/demo_run_end_epoch

screen_clear
"$SCRIPT_DIR/verify_evidence.sh" --results-only
