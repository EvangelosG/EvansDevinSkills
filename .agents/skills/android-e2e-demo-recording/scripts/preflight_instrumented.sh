#!/usr/bin/env bash
# Fail before the emulator, the build and the camera if the app module has no
# instrumented tests to record.
#
# A repo whose Compose/Espresso journeys sit in the `test` sourceset runs them
# locally under Robolectric with no device involved. connected<Variant>AndroidTest
# then succeeds having run nothing: the take is a video of an idle launcher, and
# verify_evidence.sh writes its first baseline from that empty run, so the next
# run agrees with it.
#
# Usage: preflight_instrumented.sh [--module :app]
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=_config.sh
. "$SCRIPT_DIR/_config.sh"

MODULE="$APP_MODULE"
[ "${1:-}" = "--module" ] && MODULE="$2"
DIR="${MODULE#:}"; DIR="${DIR//://}"
SRC="$REPO_ROOT/${DIR:+$DIR/}src"

# Flavoured projects put device tests in androidTest, androidTestDemo, ... .
count_tests() {  # $1 = sourceset name prefix
    find "$SRC" -maxdepth 1 -type d -name "$1*" -not -path '*/build/*' \
        -exec grep -rlE '@Test\b|@org\.junit\.Test\b' --include='*.kt' --include='*.java' {} + 2>/dev/null |
        wc -l
}

DEVICE=$(count_tests androidTest)
if [ "${DEVICE:-0}" -gt 0 ]; then
    echo "preflight: $DEVICE instrumented test file(s) under $SRC/androidTest*"
    exit 0
fi

echo "FAIL: $MODULE has no instrumented tests; there is nothing for a device to run." >&2
LOCAL_UI=$(find "$SRC" -maxdepth 1 -type d -name 'test*' -not -path '*/build/*' \
    -exec grep -rlE 'ComposeTestRule|createAndroidComposeRule|espresso|RobolectricTestRunner|@RunWith\(Robolectric' \
        --include='*.kt' --include='*.java' {} + 2>/dev/null | wc -l)
if [ "${LOCAL_UI:-0}" -gt 0 ]; then
    echo "  $LOCAL_UI UI test file(s) live in the local test sourceset instead, i.e. they run" >&2
    echo "  under Robolectric on the JVM. Those never draw on the emulator, so they cannot be" >&2
    echo "  filmed: report them from the unit XMLs, or move the journeys you want on camera" >&2
    echo "  into src/androidTest." >&2
else
    echo "  Modules that do have an androidTest sourceset:" >&2
    find "$REPO_ROOT" -type d -name 'androidTest*' -path '*/src/*' -not -path '*/build/*' \
        -printf '    %P\n' 2>/dev/null | sed 's|/src/androidTest.*||' | sort -u >&2
    echo "  Set APP_MODULE in $SKILL_DIR/config.env to one of them." >&2
fi
exit 1
