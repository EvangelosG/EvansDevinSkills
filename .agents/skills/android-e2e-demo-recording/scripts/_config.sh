#!/usr/bin/env bash
# Shared configuration. Sourced by the other scripts; not executable on its own.
#
# Nothing about a specific app belongs in the scripts. Values come from, in order
# of precedence: the environment, config.env next to this skill, then defaults
# that hold for a plain single-flavor Android project.
#
#   REPO_ROOT   repo checkout                     (default: git toplevel)
#   APP_MODULE  Gradle path of the app module     (default: :app)
#   VARIANT     capitalised variant under test    (default: Debug, e.g. DemoDebug)
#   UNIT_TASKS  space-separated unit test tasks   (default: <app>:test<Variant>UnitTest)
#   PAUSE_ARG   instrumentation arg the tests read to slow themselves down
#               for the camera                    (default: demoPauseMs)
#   AVD         emulator to boot                  (default: first `emulator -list-avds`)

SKILL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
[ -f "$SKILL_DIR/config.env" ] && . "$SKILL_DIR/config.env"

REPO_ROOT="${REPO_ROOT:-$(git -C "$SKILL_DIR" rev-parse --show-toplevel 2>/dev/null || (cd "$SKILL_DIR/../../.." && pwd))}"
APP_MODULE="${APP_MODULE:-:app}"
VARIANT="${VARIANT:-Debug}"
UNIT_TASKS="${UNIT_TASKS:-${APP_MODULE}:test${VARIANT}UnitTest}"
PAUSE_ARG="${PAUSE_ARG:-demoPauseMs}"

APP_DIR="${APP_MODULE#:}"; APP_DIR="${APP_DIR//://}"
# shellcheck disable=SC2034  # used by run_demo_suite.sh
CONNECTED_TASK="${APP_MODULE}:connected${VARIANT}AndroidTest"

# ":core:domain:testDemoDebugUnitTest" -> "core/domain/build/test-results/testDemoDebugUnitTest"
unit_results_dirs() {
    local t module task
    for t in $UNIT_TASKS; do
        task="${t##*:}"; module="${t%:*}"; module="${module#:}"; module="${module//://}"
        echo "${REPO_ROOT}${module:+/$module}/build/test-results/$task"
    done
}

# A wrong VARIANT/APP_MODULE is the likeliest way this skill fails in a new repo:
# the run dies after a full configuration phase, and the on-camera output filter
# hides Gradle's explanation. Reprint it, then say which tasks would have worked.
#   $1  the Gradle log of the failed invocation
#   $2  the regex the on-screen filter used, so an unfiltered phase is not repeated
explain_gradle_failure() {
    local log="$1" filter="${2:-}" spec task project prefix found
    echo >&2
    # The filter that keeps the video readable also swallows this block.
    echo '* What went wrong:' | grep -qE "$filter" ||
        sed -n '/^\* What went wrong:/,/^\* Try:/p' "$log" | sed '$d' >&2

    spec=$(sed -nE "s/.*Cannot locate tasks that match '([^']*)'.*/\1/p" "$log" | head -1)
    if [ -n "$spec" ]; then
        task="${spec##*:}"
        project="${spec%:*}"
        # The verb a task name starts with ("test", "assemble", "connected") is what
        # makes a useful shortlist. A misconfigured name may not have one, and an
        # unguarded no-match grep exits 1: set -e would then swallow the rest of
        # this advice, config.env pointer included.
        prefix=$(echo "$task" | grep -oE '^[a-z]+' || true)

        if grep -q "project '${project#:}' not found" "$log"; then
            echo "Modules in this build:" >&2
            (cd "$REPO_ROOT" && ./gradlew -q projects 2>/dev/null) |
                { grep -Eo "Project '[^']*'" || true; } | sed "s|Project ||;s|'||g;s|^|  |" >&2
        elif [ -n "$prefix" ] && ! grep -q 'Candidates are:' "$log"; then
            # Gradle only lists candidates for an ambiguous name, not an absent one.
            # || true: callers run under pipefail, where a no-match grep would
            # fail the assignment and abort before the config.env pointer below.
            found=$( (cd "$REPO_ROOT" && ./gradlew -q "${project}:tasks" --all 2>/dev/null) |
                grep -Eo "^${prefix}[A-Za-z0-9]*" | sort -u || true)
            if [ -n "$found" ]; then
                echo "${prefix}* tasks that exist in ${project}:" >&2
                echo "$found" | sed "s|^|  ${project}:|" >&2
            fi
        fi
        echo >&2
        echo "Set APP_MODULE / VARIANT / UNIT_TASKS to match, in:" >&2
        echo "  $SKILL_DIR/config.env" >&2
    fi
    # Gradle's own "See log for more details" means a log it does not name here.
    echo "full Gradle output: $log" >&2
}

# Instrumented XMLs land under a flavor subdirectory whose name depends on the
# variant, so find them rather than spelling the path out.
instrumented_xmls() {
    find "$REPO_ROOT/$APP_DIR/build/outputs/androidTest-results" -name 'TEST-*.xml' 2>/dev/null | sort
}
