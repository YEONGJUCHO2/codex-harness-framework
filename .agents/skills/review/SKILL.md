---
name: review
description: Use when reviewing local changes in a repository that uses Codex Harness, validating a diff, checking project guardrails, tests, CRITICAL rules, build readiness, or acting as the Harness review-only verification agent.
---

# Harness Review

Use this skill to review changes against the repository's local Harness contracts. Review findings should prioritize bugs, regressions, architecture violations, missing tests, weak tests, CRITICAL rule violations, and build/test readiness.

When invoked by `scripts/execute.py`, act as a strict review-only subagent. Do not modify implementation code. Produce a review decision and a machine-readable report.

## Inputs To Read

Before reviewing changes, read files that exist in the target repository:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- Other directly relevant `docs/*.md`
- `phases/{phase}/AGENTS.md` or `phases/{phase}/Agent.md` when present
- The step file under review
- Prior step summaries and review reports when relevant

Then inspect changed files with Git.

## Verification Commands

For step-level review, run:

```bash
npm run lint
npm run test
npm run build
```

If a command fails, the decision is `changes_requested` unless the failure is caused by missing user input, credentials, or manual setup. In that case, use `blocked`.

## Checklist

Check these items:

1. **Requirement compliance**: do changes satisfy the step and stay within the PRD or equivalent requirement document?
2. **Architecture compliance**: do changed files follow the structure defined in `ARCHITECTURE.md` and phase rules?
3. **Stack compliance**: do changes stay within decisions in `ADR.md`?
4. **Tests**: are tests present and meaningful for new or changed behavior?
5. **CRITICAL rules**: do changes avoid violating CRITICAL rules in root and phase `AGENTS.md`?
6. **Buildability**: do the verification commands pass?
7. **Maintainability**: is the implementation coherent, localized, and free of unnecessary abstraction?
8. **Docs drift**: did the change introduce architectural or operational knowledge that belongs in docs or phase rules?

## Decision

Use exactly one:

- `approved`: commands pass, requirements are met, tests are meaningful, and no blocker/major findings remain.
- `changes_requested`: the implementation can be fixed by another implementation pass.
- `blocked`: user input, credentials, manual setup, or an external state change is required.

Review-requested changes are not implementation-attempt failures. They consume review cycles.

## Output

For human code review requests, lead with concrete findings ordered by severity and include file/line references. If there are no findings, say so explicitly.

Then include this checklist table:

| Item | Result | Notes |
| --- | --- | --- |
| Requirement compliance | pass/fail | {detail} |
| Architecture compliance | pass/fail | {detail} |
| Stack compliance | pass/fail | {detail} |
| Tests | pass/fail | {detail} |
| CRITICAL rules | pass/fail | {detail} |
| Buildability | pass/fail | {detail} |
| Maintainability | pass/fail | {detail} |
| Docs drift | pass/fail | {detail} |

When invoked by the Harness executor, write the requested JSON report and do not modify implementation files. The report should include:

```json
{
  "decision": "approved | changes_requested | blocked",
  "summary": "short review summary",
  "commands": [
    { "cmd": "npm run lint", "exitCode": 0, "summary": "result" },
    { "cmd": "npm run test", "exitCode": 0, "summary": "result" },
    { "cmd": "npm run build", "exitCode": 0, "summary": "result" }
  ],
  "findings": [
    {
      "severity": "blocker | major | minor",
      "file": "path",
      "line": 1,
      "message": "specific issue"
    }
  ],
  "required_changes": ["actionable change request"]
}
```
