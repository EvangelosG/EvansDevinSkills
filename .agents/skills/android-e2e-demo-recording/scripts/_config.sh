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

# Instrumented XMLs land under a flavor subdirectory whose name depends on the
# variant, so find them rather than spelling the path out.
instrumented_xmls() {
    find "$REPO_ROOT/$APP_DIR/build/outputs/androidTest-results" -name 'TEST-*.xml' 2>/dev/null | sort
}
