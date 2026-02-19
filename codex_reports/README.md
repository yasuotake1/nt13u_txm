# codex_reports

This directory contains machine-generated verification reports produced by Codex.

These reports are **analysis artifacts only**.
They do not represent approved changes to the codebase.

---

## Purpose

The purpose of `codex_reports/` is to:

- Log repository-wide checks against `docs/PRINCIPLES.md`
- Provide traceable PASS/FAIL results with evidence
- Preserve historical verification results
- Enable architectural review without modifying source code

Codex is used as a verification engine.
Human review and final implementation decisions remain manual.

---

## What is Allowed Here

Codex may:

- Create new report files under `codex_reports/`
- Append additional reports for new commits
- Update this README if the reporting protocol changes

Codex must NOT:

- Modify any files under `src/`
- Modify `docs/` (except this README if protocol changes)
- Commit changes outside `codex_reports/`

If unintended modifications occur, they must be reverted.

---

## Report Naming Convention

Report files must follow:

YYYYMMDD_principles_check__<short_commit_sha>.json

Example:

20260219_principles_check__a1b2c3d.json

Each report must contain:

- date
- repo_commit (full SHA)
- principles_file reference
- invariant results:
  - id
  - status (PASS / FAIL / UNKNOWN)
  - reason
  - evidence (file + line range)
  - minimal_fix_strategy (if FAIL)
- commands_used

---

## Workflow

1. Codex reads `docs/PRINCIPLES.md`.
2. Codex verifies current implementation.
3. Codex writes a JSON report under `codex_reports/`.
4. Codex commits the report to `main`.
5. Human reviews results.
6. Human decides whether and how to modify the code.

Codex does NOT automatically fix the code in this workflow.

---

## Philosophy

- Architecture is defined in `docs/ARCHITECTURE.md`.
- System constraints and invariants are defined in `docs/PRINCIPLES.md`.
- Codex checks compliance.
- Humans control design decisions.

This directory exists to make verification explicit, traceable, and reversible.
