---
name: review
description: Use when reviewing local changes in a repository that uses Codex Harness, validating a diff, checking project guardrails, tests, CRITICAL rules, or build readiness.
---

# Harness Review

Use this skill to review changes against the repository's local Harness contracts. Review findings should prioritize bugs, regressions, architecture violations, missing tests, and build/test readiness.

## Inputs To Read

Before reviewing changes, read files that exist in the target repository:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- Other directly relevant `docs/*.md`

Then inspect changed files with Git.

## Checklist

Check these items:

1. **Requirement compliance**: do changes stay within the PRD or equivalent requirement document?
2. **Architecture compliance**: do changed files follow the structure defined in `ARCHITECTURE.md`?
3. **Stack compliance**: do changes stay within decisions in `ADR.md`?
4. **Tests**: are tests present for new behavior or changed behavior?
5. **CRITICAL rules**: do changes avoid violating CRITICAL rules in `AGENTS.md`?
6. **Buildability**: do validation commands pass?

Run validation commands when appropriate for the requested review scope. If a command cannot be run, state that clearly.

## Output

For code review requests, lead with concrete findings ordered by severity and include file/line references. If there are no findings, say so explicitly.

Then include this checklist table:

| Item | Result | Notes |
| --- | --- | --- |
| Requirement compliance | pass/fail | {detail} |
| Architecture compliance | pass/fail | {detail} |
| Stack compliance | pass/fail | {detail} |
| Tests | pass/fail | {detail} |
| CRITICAL rules | pass/fail | {detail} |
| Buildability | pass/fail | {detail} |

If there are violations, propose concrete fixes.
