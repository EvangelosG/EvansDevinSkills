#!/usr/bin/env bash
# Propose the config.env values for the repo in REPO_ROOT, so a new repo does not
# have to be configured by guessing and then reading a Gradle stack trace.
#
# Usage: detect_config.sh [--write]
#   --write   replace the five values in config.env with what was detected
#
# Everything printed is derived from the checkout and from the app module's own
# task list; nothing is hard coded per app.
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=_config.sh
. "$SCRIPT_DIR/_config.sh"
cd "$REPO_ROOT" || exit 1

WRITE=0
[ "${1:-}" = "--write" ] && WRITE=1

say() { echo "$*" >&2; }

gradle_path_of() {  # "./feature/foo/build.gradle.kts" -> ":feature:foo"
    local d; d=$(dirname "${1#./}")
    [ "$d" = "." ] && { echo ":"; return; }
    echo ":${d//\//:}"
}

# ---- app module: the one module that applies the application plugin ----------
# A library module has connected<Variant>AndroidTest tasks too, so picking by
# task name alone would happily point the whole run at :core:data.
# Three things also mention the plugin without being an app: the root build file
# (`alias(...) apply false`), a convention plugin under build-logic that registers
# it, and any module that names it in a comment. Hence plugin syntax, minus
# `apply false`, minus build-logic.
application_modules() {
    find . \( -name 'build.gradle' -o -name 'build.gradle.kts' \) \
        -not -path '*/build/*' -not -path './build-logic/*' -print |
        while read -r f; do
            grep -E '^[[:space:]]*(id[[:space:]("'\'']|apply[[:space:]]+plugin:|alias[[:space:]]*\()' "$f" |
                grep -E 'com\.android\.application|\.android\.application|plugins\..*application' |
                grep -qv 'apply[[:space:]]\+false' && gradle_path_of "$f"
        done | sort -u
}
mapfile -t APP_MODULES < <(application_modules)
if [ "${#APP_MODULES[@]}" -eq 0 ]; then
    say "no module applies com.android.application under $REPO_ROOT"
    say "APP_MODULE has to be set by hand in $SKILL_DIR/config.env"
    exit 1
fi
# Sample/catalog apps are application modules too, and sort before the real one
# as often as not. The module with device tests is the only one worth filming.
DET_APP_MODULE=""
for m in "${APP_MODULES[@]}"; do
    "$SCRIPT_DIR/preflight_instrumented.sh" --module "$m" >/dev/null 2>&1 &&
        { DET_APP_MODULE="$m"; break; }
done
DET_APP_MODULE="${DET_APP_MODULE:-${APP_MODULES[0]}}"
if [ "${#APP_MODULES[@]}" -gt 1 ]; then
    say "application modules: ${APP_MODULES[*]} (chose $DET_APP_MODULE)"
fi

# ---- variant: ask the module which connected tasks it actually has -----------
# Flavors can come from a convention plugin or a version catalog, so reading the
# build file is not enough; the task list is the only answer that cannot be wrong.
say "asking Gradle for ${DET_APP_MODULE}'s connected test tasks (~30s)..."
mapfile -t VARIANTS < <(
    ./gradlew -q "${DET_APP_MODULE}:tasks" --all 2>/dev/null |
        grep -Eo '\bconnected[A-Za-z0-9]+AndroidTest\b' |
        sed -E 's/^connected(.*)AndroidTest$/\1/' | grep -v '^$' | sort -u
)
if [ "${#VARIANTS[@]}" -eq 0 ]; then
    say "no connected<Variant>AndroidTest task in $DET_APP_MODULE; is it really the app module?"
    DET_VARIANT="Debug"
else
    # Debug builds are the testable ones; a release variant needs signing config.
    DET_VARIANT=$(printf '%s\n' "${VARIANTS[@]}" | grep -i 'debug' | head -1)
    DET_VARIANT="${DET_VARIANT:-${VARIANTS[0]}}"
    [ "${#VARIANTS[@]}" -gt 1 ] && say "variants available: ${VARIANTS[*]} (chose $DET_VARIANT)"
fi

# ---- unit tasks: modules that have a local test sourceset --------------------
# The app module's own task is the default; other modules are printed as a
# shortlist because which of them are worth showing on camera is a judgement call.
mapfile -t UNIT_MODULES < <(
    find . -type d -name test -path '*/src/*' -not -path '*/build/*' 2>/dev/null |
        sed -E 's|/src/test$||' | sort -u |
        while read -r d; do
            find "$d/src/test" -name '*.kt' -o -name '*.java' 2>/dev/null | head -1 | grep -q . || continue
            # A plain JVM module has :test; only an Android module has variants.
            if grep -qhE 'com\.android\.|\.android\.(library|application)' "$d"/build.gradle* 2>/dev/null; then
                echo "$(gradle_path_of "$d/build.gradle"):test${DET_VARIANT}UnitTest"
            else
                echo "$(gradle_path_of "$d/build.gradle"):test"
            fi
        done
)

# ---- androidTest: is there anything on the device to record? -----------------
"$SCRIPT_DIR/preflight_instrumented.sh" --module "$DET_APP_MODULE" >&2 || true

cat <<EOF
APP_MODULE="\${APP_MODULE:-$DET_APP_MODULE}"
VARIANT="\${VARIANT:-$DET_VARIANT}"
UNIT_TASKS="\${UNIT_TASKS:-}"             # empty = <APP_MODULE>:test<VARIANT>UnitTest
PAUSE_ARG="\${PAUSE_ARG:-demoPauseMs}"
AVD="\${AVD:-}"
EOF
if [ "${#UNIT_MODULES[@]}" -gt 0 ]; then
    echo "# modules with a local test sourceset, if you want more than the app's own:"
    for m in "${UNIT_MODULES[@]}"; do echo "#   $m"; done
fi

if [ "$WRITE" = 1 ]; then
    CONF="$SKILL_DIR/config.env"
    cp "$CONF" "$CONF.bak"
    sed -i -E \
        -e "s|^APP_MODULE=.*|APP_MODULE=\"\\\${APP_MODULE:-$DET_APP_MODULE}\"|" \
        -e "s|^VARIANT=.*|VARIANT=\"\\\${VARIANT:-$DET_VARIANT}\"|" \
        "$CONF"
    say "updated $CONF (previous copy at $CONF.bak)"
fi
