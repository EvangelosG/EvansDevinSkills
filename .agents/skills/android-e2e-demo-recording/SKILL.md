---
name: android-e2e-demo-recording
description: Run an Android app's unit + instrumented (Compose) tests on a Devin box, and record a single continuous side-by-side demo video of them. Use when asked to run the Android tests, verify them on an emulator, or produce a recording/demo of a test run.
---

# Android tests on a Devin box: run them, and record them

Two jobs live here. **If you only need results, stop after [Run and verify](#run-and-verify)** —
everything below it is for producing a watchable demo and costs another ~10 minutes.

Scripts do the work; this file explains when and why. All paths are relative to the repo root.

## Nothing here is app-specific

This skill lives in a shared skills repo: copy `.agents/skills/android-e2e-demo-recording/` into the
Android repo you are working in and edit `config.env`. That is the whole port.

The scripts take module names, variant, tasks and AVD from `config.env` next to this file (environment
variables override it); everything else — result-XML locations, test names, test count, the labels on
the video — is discovered at runtime from Gradle output, the result XMLs, and `adb logcat`.

```bash
APP_MODULE=":app"                # Gradle path of the app module
VARIANT="Debug"                  # capitalised variant; flavoured projects use e.g. "DemoDebug"
UNIT_TASKS=""                    # default: <app>:test<Variant>UnitTest
PAUSE_ARG="demoPauseMs"          # instrumentation arg the tests read to slow down for the camera
AVD=""                           # default: the first installed AVD
```

Getting one of those five wrong is the normal way this skill fails in a new repo, so the scripts turn
that into an answer rather than a Gradle stack trace: a bad `VARIANT`/`UNIT_TASKS` prints the tasks that
do exist in the project Gradle looked in, a bad `APP_MODULE` prints the modules in the build, a missing
result XML prints the directories that do have results, and a bad `AVD` prints the installed ones. The
full Gradle output of the failed phase is kept in `/tmp/demo_gradle.log` — the on-camera filter shows
only a few lines of it.

The scripts take the repo under test to be the one they live in. `REPO_ROOT=/path/to/app-repo` overrides
that, so you can also drive another checkout straight from this skills repo without copying anything;
only the gitignored `baseline_testcases.txt` is written next to the skill.

## Read this first: the three traps

1. **The screen recorder time lapses its own `*-edited.mp4`** (a 200s take becomes ~18s). Always
   re-encode the raw `*-raw-*.mkv` chunks instead — `scripts/finalize_recording.sh` does this and
   `scripts/verify_evidence.sh --video` fails the take if the duration does not match the run.
2. **Compose journeys are near-instant.** A desktop capture at default speed shows each screen for a
   single frame, and a screenshot after the run only catches the launcher. The run must be slowed with
   `demoPauseMs` (below) or there is nothing to see.
3. **Gradle marks test tasks UP-TO-DATE**, so a recorded "run" can execute zero tests. Pass `--rerun`
   per task and always confirm against the result XML, never against the console.

Two smaller ones that cost a whole take each: the emulator must be started with `setsid` or it dies
with the shell that launched it (it looks like a clean boot followed by "no emulator window"), and
`clear` fails when `TERM` is unset, which aborts a `set -e` script mid-run.

## Cost and timing

| Phase | Cold | Warm |
| --- | --- | --- |
| Emulator boot | ~40s | — |
| Pre-warm build (`--prewarm`) | 5-10 min | ~30s |
| Unit tasks | ~1 min | ~2s |
| `$APP_MODULE:connected${VARIANT}AndroidTest` | ~4 min | ~1m10s |
| Full on-camera take | — | ~2.5 min |

Always pre-warm off camera. An un-warmed take is a five minute video of a Gradle build.

## Prerequisites

Provisioned by the repo blueprint; verify rather than assume:
- JDK 21 (`JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`). JDK 17 fails Robolectric/AGP with
  "Android SDK 36 requires Java 21".
- Android SDK 36 and at least one AVD. The emulator needs KVM, so it must be launched via `sg kvm -c`
  (see `scripts/boot_emulator.sh`) — the session shell does not inherit the kvm group.
- `wmctrl`, `xdotool`, `ffmpeg`, `konsole` for the recording half.

## Run and verify

```bash
S=.agents/skills/android-e2e-demo-recording/scripts
$S/boot_emulator.sh                     # idempotent; waits for sys.boot_completed, not just adb
$S/run_demo_suite.sh --prewarm          # build everything first
$S/run_demo_suite.sh
$S/verify_evidence.sh
```

`verify_evidence.sh` is the definition of done for the results half:
- instrumented `TEST-*.xml` exists, 0 failures, 0 errors;
- every `testcase name=` is listed, so a filter that silently matched nothing is caught;
- the test *set* is diffed against `baseline_testcases.txt` rather than against a count hard coded in
  the doc, so the baseline cannot rot and a real regression cannot hide behind a stale number. That
  file is written on the first run and gitignored, not committed: it must describe the branch you are
  on;
- unit XMLs report `failures="0" errors="0"`.

Note that the instrumented count includes `@Ignore`d tests while the logcat count does not, so
`Starting 12 tests` and `run finished: 11 tests, 0 failed, 1 ignored` agreeing is normal — only the 11
that execute can be labelled on the video.

Result files, if you need them directly:
- unit: `<module>/build/test-results/test<Variant>UnitTest/*.xml`
- instrumented: under `<app>/build/outputs/androidTest-results/`, in a flavor subdirectory whose name
  depends on the variant — `_config.sh` finds them rather than spelling the path out

Useful ad-hoc invocations:
- one class: `./gradlew $APP_MODULE:connected${VARIANT}AndroidTest -Pandroid.testInstrumentationRunnerArguments.class=<FQCN>`
- one method: append `#methodName` to the same property (warm re-run ~15s)

## Record a demo

Deliverable: **exactly one** 1x mp4 showing the emulator and the Gradle console side by side, recorded
in one unbroken take. Extra device-only captures confuse reviewers.

```bash
S=.agents/skills/android-e2e-demo-recording/scripts
$S/boot_emulator.sh
$S/run_demo_suite.sh --prewarm          # off camera
$S/place_windows.sh                     # derives geometry from the actual display
# in the konsole that just opened, make it readable on video:
#   printf '\033]50;FontSize=16\a'; clear
# start the screen recording, then in that same konsole and nothing else:
$S/run_demo_suite.sh                    # add --pause-ms 800 for a slower, longer take
# stop the recording; the chunks land in ~/screencasts/<recording-id>/
$S/finalize_recording.sh ~/screencasts/<recording-id> take_1x.mp4   # also writes /tmp/video_start_epoch
$S/label_video.sh take_1x.mp4 take_1x_labelled.mp4
$S/verify_evidence.sh --video take_1x_labelled.mp4
```

Run `verify_evidence.sh` before anything else touches the device: every run overwrites the result XMLs
and the wall-clock files it reads, so a later run makes it judge the shipped take against the wrong
numbers.

Do not try to note the recording's start time by hand: the recorder is already capturing while you type,
and that gap (5s on one take here, arbitrary in general) drifts every label by two or three tests.
`finalize_recording.sh` takes it from the first chunk's creation time instead.

`--prewarm` exits as soon as it is parsed, so run it on its own — combining it with `--pause-ms`
silently drops the other flag.

### Why each piece exists

**Window placement is derived, not fixed.** The emulator window keeps the device aspect ratio: asking for
a wide window at full height yields something much narrower (504px wide at 1120px tall on a 1600x1200
desktop). `place_windows.sh` therefore requests full height, measures the result with `wmctrl -lG`, and
starts the terminal past the emulator's floating side-toolbar (a separate window — keep it clear). It
polls for windows instead of sleeping, so it does not race konsole's startup, and it works on a display
of any size.

**Pauses come from the tests, opt-in.** This is the one part of the skill that needs a change in the app
repo: a UI test class opts in by reading `$PAUSE_ARG` (`demoPauseMs` by default):

```kotlin
private val demoPauseMs: Long =
    InstrumentationRegistry.getArguments().getString("demoPauseMs")?.toLongOrNull() ?: 0L

private fun demoPause() { if (demoPauseMs > 0) Thread.sleep(demoPauseMs) }

@After  // rests on each journey's end state so consecutive tests are distinguishable
fun holdFinalState() { if (demoPauseMs > 0) Thread.sleep(maxOf(demoPauseMs * 2, 3_000L)) }
```

It defaults to 0, so CI, normal runs and the default take are untouched, and classes that ignore the
argument still run normally. **Pausing is off by default**: on nowinandroid's 11 navigation tests, 800ms
turned a ~23s run into ~80s, and a 100s video of the same eleven assertions is a worse artifact than a
40s one where the labels carry the narration. Reach for `--pause-ms` only when a reviewer has to read the
screens themselves.

When you do, note that the final hold has its own floor rather than scaling with the pause: the mid-test
pauses set the pace, while the end state has to survive the ~3 consecutive 1fps frames below whatever
pace you pick. Scaling it (`pause * 2`) gave 800ms a 1.6s hold that could not span them, i.e. it forced a
slow run just to get a readable ending.

Add the same three pieces to any UI test class you want to demo, and call `demoPause()` after each
meaningful assertion — a journey with no pauses is invisible in the video.

**Labels are derived after the run, from timestamps.** `run_demo_suite.sh` starts an
`adb logcat -v epoch -s TestRunner:I` watcher; `annotations_from_log.sh` turns that into
`<class> <method> <start-offset> <end-offset>`. Offsets are relative to whatever epoch file you pass;
its own default is the *run* start, while `label_video.sh` defaults to `/tmp/video_start_epoch` so its
offsets are video time.

Burn them into the video with `ffmpeg drawtext`; that is the default, because `annotate_recording` can
only stamp the *current* moment of a live recording — there is no way to apply post-run offsets, and a
tool round-trip is 1-2s. Live annotation is therefore only viable when `demoPauseMs` stretches each test
to ~10s or more. When you do annotate live, emit **one `test_start` plus one grouped assertion per
test** — the number of annotations is what the UI reports as the test count, which is why phase-level
markers once surfaced a 19-test run as "2 tests passed". Test execution order is not source order; read
it from the log.

`label_video.sh` builds one `drawtext` filter per row of `annotations_from_log.sh` and burns the name of
the running test into its own time window, at the foot of the emulator pane (`place_windows.sh` leaves
its geometry in `/tmp/demo_emulator_geometry`, and long names are scaled down to fit). No test name
appears anywhere in the skill: they come out of the device log, so the overlay follows whatever the app
actually ran.

**Device-only capture** is an alternative when the terminal is not needed (crisper, but loses the
console): `adb shell screenrecord` writes ~180s per file, so loop segments and concat them.

```bash
i=0; touch /tmp/recflag
while [ -f /tmp/recflag ]; do
    adb shell screenrecord --time-limit 180 --bit-rate 8000000 "/sdcard/demo_seg_$i.mp4"
    i=$((i+1))
done
# stop with: rm /tmp/recflag; adb shell pkill -l 2 screenrecord   (SIGINT so the mp4 is finalised)
adb pull /sdcard/  ./device-segments
printf "file '%s'\n" ./device-segments/demo_seg_*.mp4 > /tmp/list.txt
ffmpeg -f concat -safe 0 -i /tmp/list.txt -c copy device.mp4
```

### Before you ship the video

`verify_evidence.sh --video take_1x.mp4` checks the results, and checks the video duration against the
measured wall clock in both directions (too short = the time-lapsed export; more than 2x = untrimmed
idle or the wrong chunks). It cannot judge watchability, so eyeball the contact sheet that
`finalize_recording.sh` wrote: every test should appear on it as a distinct screen under its own label.

The default pace does not clear that bar and is not meant to. Measured on nowinandroid: 11 tests in ~21s
is 1-2s each, several of them showing the same screen, and a test whose window is entirely app restart
gets a label over the launcher. Ship the default take as evidence that the suite ran green; for a video
someone is expected to *watch*, add `--pause-ms 800` (every test 4-9s with a held end state) or 400 for a
middle ground.

On a `--pause-ms` take, hold each journey's end state for ~3+ consecutive one-second frames. Check that
with a per-pixel tolerance (max delta ~8) rather than by hashing frames: `libx264 crf 26` perturbs a
perfectly still screen by a few grey levels on a handful of pixels, so byte-identity fails on encoder
noise while the hold is plainly there. Hashing found 3 identical frames in 2 of 11 windows on a take
where the tolerant comparison found 4-6 in all 11.

```bash
ffmpeg -ss 95 -to 155 -i take_1x.mp4 -vf "fps=1,crop=520:1130:0:20,scale=150:-1,tile=15x4" -frames:v 1 sheet.png
```

Trim idle at **both** ends before labelling, then regenerate the contact sheet — the finalizer's sheet
samples the untrimmed file, so any tail you leave on eats the tiles. Budget for this: the duration guard
allows 2x the run, which at the ~32s default pace is only ~30s of head and tail combined, and the gap
between the run finishing and someone stopping the recorder eats that easily. Ship one mp4.

```bash
ffmpeg -y -ss 12 -to 56 -i take_1x.mp4 -c:v libx264 -crf 26 trimmed.mp4
$S/label_video.sh trimmed.mp4 take_1x_labelled.mp4 --trim-head 12   # or the labels lead by 12s
```

Expect the console pane to sit empty for the first ~25s: each phase clears the screen and only its
summary lines survive the filter. That is the filter working, not a failed capture.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `/dev/kvm permission denied` | Launch through `sg kvm -c` (`boot_emulator.sh`), not directly. |
| `adb wait-for-device` returns but the screen is black | Boot is not finished; poll `sys.boot_completed`. |
| No emulator window on screen | `DISPLAY` unset; export `DISPLAY=:0` before emulator and wmctrl. |
| `adb` reports no devices after a box restart | Caches survive restarts, the emulator/konsole/adb server do not. Re-run boot + placement. |
| Test tasks print `UP-TO-DATE`, video shows nothing | Missing `--rerun` per task. |
| "configuration cache discarded" on connected tests | Expected (OSS-licenses task), not a failure. |
| `screenrecord` stops early | ~180s per file limit, and check free space on `/sdcard`. |
| Console floods with `preBuild UP-TO-DATE` | Use `grep -E`, not `-Ei`: case-insensitive `BUILD` matches everything. |
| Windows overlap or hide under the panel | Re-run `place_windows.sh`; it re-measures and re-places. |
| `ffmpeg: Impossible to open '/tmp/...-raw-000.mkv'` | The concat list must sit beside the chunks or hold absolute paths; `finalize_recording.sh` does this. |

## Who runs this

The testing agent owns the whole procedure (boot, build, windowing, recording) and hands back:
the single `take_1x.mp4` path, the `verify_evidence.sh` output, and the annotation list. The main agent
attaches those to the user or the PR — it should not re-run any of this itself.

## Devin Secrets Needed

None.
