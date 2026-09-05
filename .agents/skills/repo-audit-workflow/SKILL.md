---
name: repo-audit-workflow
description: Audit a repo's source files with a Devin dynamic workflow — one agent per file in parallel, then a consolidated review document and PR. Use when asked to review/audit a codebase broadly, or for a demo of dynamic workflows.
---

# Repo audit as a dynamic workflow

Fans out one agent per source file (read-only, on this machine), then feeds all
the structured findings to a single agent that writes a consolidated review
document and opens a PR.

Two phases:

| Phase | Agents | Where | Does |
| --- | --- | --- | --- |
| `analyze` | one per file | shared VM (this machine, `lite` mode) | reads a single file, returns `{file, purpose, findings[]}` |
| `report` | one | separate VM, `repos=[AUDIT_REPO]` | consolidates findings into `docs/code-review.md`, opens a PR |

The file inventory is derived deterministically from `git ls-files` inside the
script, so a resumed run (`run_workflow` with the previous `run_id`) replays the
same agents instead of re-running them.

## Use it

1. Make sure the repo is cloned on this machine — the `analyze` agents read the
   local working tree.
2. Run it, setting config through the environment:

```bash
AUDIT_REPO=github.com/owner/name AUDIT_LOCAL=/home/ubuntu/repos/name \
  # then call run_workflow with script_path=<this dir>/workflow.py
```

`run_workflow` executes the script on this machine, so exported variables in the
session's environment apply. Set them with the `env` argument of a shell call
that exports them, or edit the defaults at the top of `workflow.py`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AUDIT_REPO` | *(required)* | Repo the `report` agent clones, e.g. `github.com/owner/name` |
| `AUDIT_LOCAL` | current directory | Local checkout the `analyze` agents read |
| `AUDIT_GLOBS` | common source extensions | Comma-separated globs to include |
| `AUDIT_EXCLUDE_GLOBS` | vendor/test paths | Comma-separated globs to skip |
| `AUDIT_MAX_FILES` | `12` | Cap on fan-out width (largest files win) |
| `AUDIT_FOCUS` | `correctness, robustness, and security` | What the auditors look for |
| `AUDIT_REPORT_PATH` | `docs/code-review.md` | Where the review document is written |
| `AUDIT_OPEN_PR` | `true` | `false` pushes a branch without opening a PR |
| `AUDIT_ANALYZE_MODE` | `lite` | Devin mode for the per-file agents |

## Notes

- The `analyze` agents share this machine's filesystem and are instructed to be
  strictly read-only and to stay inside their one assigned file, so they cannot
  collide with each other or with your working tree.
- Widening `AUDIT_MAX_FILES` is cheap in wall time (fan-out is throttled, not
  serialized) but not in ACUs — each file is an agent.
- Reference run: 6 files, 14 findings, ~2 min, 2.19 ACUs for the report agent
  (shared-VM agents bill to the parent session).
