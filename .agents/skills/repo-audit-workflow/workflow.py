"""Fan-out code audit as a Devin dynamic workflow.

Run with the `run_workflow` tool, passing this file's absolute path as
`script_path`. Configuration comes from environment variables (see SKILL.md);
the runtime shim provides register_workflow/agent/parallel/log.
"""

import asyncio
import fnmatch
import json
import os
import subprocess

REPO = os.environ.get("AUDIT_REPO", "").strip()
LOCAL = os.path.abspath(os.environ.get("AUDIT_LOCAL", os.getcwd()))
GLOBS = [g.strip() for g in os.environ.get(
    "AUDIT_GLOBS",
    "*.js,*.jsx,*.ts,*.tsx,*.py,*.go,*.rb,*.java,*.kt",
).split(",") if g.strip()]
EXCLUDES = [g.strip() for g in os.environ.get(
    "AUDIT_EXCLUDE_GLOBS",
    "*/node_modules/*,*/__tests__/*,*/test/*,*/tests/*,*_test.go,*.min.js",
).split(",") if g.strip()]
MAX_FILES = int(os.environ.get("AUDIT_MAX_FILES", "12"))
FOCUS = os.environ.get(
    "AUDIT_FOCUS",
    "correctness, robustness, and security",
)
OPEN_PR = os.environ.get("AUDIT_OPEN_PR", "true").lower() not in ("false", "0", "no")
REPORT_PATH = os.environ.get("AUDIT_REPORT_PATH", "docs/code-review.md")
ANALYZE_MODE = os.environ.get("AUDIT_ANALYZE_MODE", "lite")

if not REPO:
    raise SystemExit("AUDIT_REPO is required, e.g. github.com/owner/name")


def inventory():
    """Deterministically enumerate the files to audit from git's index."""
    tracked = subprocess.run(
        ["git", "-C", LOCAL, "ls-files"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    picked = [
        path for path in tracked
        if any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(os.path.basename(path), g)
               for g in GLOBS)
        and not any(fnmatch.fnmatch("/" + path, e) or fnmatch.fnmatch(path, e)
                    for e in EXCLUDES)
    ]
    # Largest files first (most to audit), tie-broken by path for stable hashes.
    picked.sort(key=lambda p: (-os.path.getsize(os.path.join(LOCAL, p)), p))
    return sorted(picked[:MAX_FILES])


FILES = inventory()

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "purpose": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string"},
                    "issue": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
            },
        },
    },
    "required": ["file", "purpose", "findings"],
}

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "pr_url": {"type": "string"},
        "branch": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["pr_url", "branch", "summary"],
}

META = {
    "name": "repo-audit-workflow",
    "description": (
        "Audit one source file per agent in parallel, then consolidate the "
        "findings into a review document" + (" and open a PR." if OPEN_PR else ".")
    ),
    "product": REPO,
    "soft_time_limit_minutes": 10,
    "phases": [
        {
            "title": "analyze",
            "detail": "one shared-VM agent per source file, read-only audit",
            "count": len(FILES),
            "labels": [f"analyze-{f}" for f in FILES],
            "soft_time_limit_minutes": 8,
        },
        {
            "title": "report",
            "detail": (
                f"separate-VM agent writes {REPORT_PATH}"
                + (" and opens a PR" if OPEN_PR else "")
            ),
            "count": 1,
            "labels": ["report"],
            "soft_time_limit_minutes": 20,
        },
    ],
}


async def analyze(path):
    prompt = (
        f"You are auditing one file of the repository checked out on this "
        f"machine at {LOCAL}.\n\n"
        f"Read ONLY this file: {LOCAL}/{path}. You may also read the repo's "
        "README/AGENTS.md/CLAUDE.md for context. Do NOT edit any file, do not "
        "start servers, do not switch git branches, and do not touch anything "
        "outside that file.\n\n"
        f"Focus on: {FOCUS}.\n\n"
        "Report: a one-sentence description of the file's purpose, and a list "
        "of concrete findings. For each finding give severity "
        "(high/medium/low), the issue, and a specific suggested fix. Return an "
        "empty findings list if the file is clean; do not invent problems."
    )
    try:
        result = await agent(  # noqa: F821 - runtime shim
            prompt,
            phase="analyze",
            schema=FINDINGS_SCHEMA,
            label=f"analyze-{path}",
            mode=ANALYZE_MODE,
            vm_mode="shared",
        )
    except WorkflowAgentError as exc:  # noqa: F821 - runtime shim
        log(f"analyze failed for {path}: {exc}")  # noqa: F821
        return {"file": path, "purpose": "(agent failed)", "findings": []}
    log(f"analyzed {path}: {len(result.get('findings') or [])} finding(s)")  # noqa: F821
    return result


async def report(all_findings):
    payload = json.dumps(all_findings, sort_keys=True, indent=2)
    pr_clause = (
        "Open a PR titled 'Add workflow-generated code review document' and "
        "report the PR URL, branch name, and a one-line summary."
        if OPEN_PR else
        "Do not open a PR: push the branch only, and report the branch name, "
        "an empty pr_url, and a one-line summary."
    )
    prompt = (
        f"Repository: {REPO}. A fan-out of per-file audits produced the JSON "
        "findings below.\n\n"
        f"{payload}\n\n"
        "Task: create a new branch off the default branch and add a markdown "
        f"document at {REPORT_PATH} consolidating these findings — a short "
        "intro noting it was produced by a Devin dynamic workflow, a summary "
        "table of findings by severity, then one section per file with its "
        "purpose and each finding (issue + suggested fix). Drop duplicates and "
        "anything that is clearly wrong once you check the code yourself. Do "
        f"NOT change any application code. {pr_clause}"
    )
    return await agent(  # noqa: F821 - runtime shim
        prompt,
        phase="report",
        schema=REPORT_SCHEMA,
        label="report",
        repos=[REPO],
    )


async def main():
    await register_workflow(META)  # noqa: F821 - runtime shim
    if not FILES:
        log("no files matched AUDIT_GLOBS - nothing to audit")  # noqa: F821
        return
    log(f"auditing {len(FILES)} file(s) in {REPO}")  # noqa: F821
    findings = await parallel([lambda p=p: analyze(p) for p in FILES])  # noqa: F821
    total = sum(len(f.get("findings") or []) for f in findings)
    log(f"analyze phase done: {total} finding(s) across {len(FILES)} file(s)")  # noqa: F821
    result = await report(findings)
    log(f"report: {result['pr_url'] or result['branch']}")  # noqa: F821


asyncio.run(main())
