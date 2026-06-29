# Harness Workflow Contract

This document defines the portable workflow boundary for repositories that copy the Codex Harness Framework.

## Goal

A concrete user command can authorize the Harness to carry implementation work through a GitHub PR and, when requested, merge that PR after checks pass. The Harness should automate repeatable coding and verification steps, while keeping product direction, production operations, credentials, destructive actions, and final external records under human control.

## Default flow

1. Confirm repository status and phase scope.
2. Create or check out `feat-{phase}`.
3. Run implementation sessions for pending steps.
4. Require each implementation session to stop at `ready_for_review`; implementation sessions must not mark steps `completed` or create commits.
5. Run a separate review-only session for each step.
6. Review sessions run the official verification commands and write JSON reports.
7. Only `scripts/execute.py` marks a reviewed step `completed` and creates commits.
8. Run phase evaluation after every step is approved.
9. Finalize phase metadata after phase evaluation approves the increment.
10. Depending on the requested release mode:
    - local only: stop after local phase completion,
    - `--push`: push the phase branch,
    - `--pr`: push and create or reuse a GitHub PR,
    - `--merge`: push, create or reuse a PR, wait for checks, and merge only when checks pass.

## Release modes

```bash
python3 scripts/execute.py {phase}
python3 scripts/execute.py {phase} --push
python3 scripts/execute.py {phase} --pr
python3 scripts/execute.py {phase} --merge
```

Optional PR/merge controls:

```bash
python3 scripts/execute.py {phase} --merge --base main --merge-method merge --checks-timeout 900
```

Supported merge methods are `merge`, `squash`, and `rebase`. The default is `merge` so phase step commits remain visible unless the target project chooses a different policy.

## Merge gate

The Harness must not force-merge.

`--merge` means:

- push the phase branch,
- create or reuse an open PR for the branch,
- run `gh pr checks --watch --fail-fast`,
- merge only if checks pass,
- stop and report if checks fail, time out, or the PR cannot merge cleanly.

## Human-gated boundaries

The Harness must stop or block when a task requires any of the following unless the user separately and explicitly approves that boundary:

- manual production deploys, production alias changes, or production infrastructure mutations,
- credentials, secrets, tokens, or environment-value changes,
- destructive database operations,
- git history rewrites or force pushes,
- final external durable records such as scoreboards, next-prompt steering files, Engineering Reports, or project-memory notes outside the repository.

A phase evaluator or PR body may draft suggested scores, risks, follow-ups, and next prompts, but final external durable records are human-approved artifacts, not automatic Harness side effects.

## What belongs in the Harness

| Concern | Harness-owned? | Notes |
| --- | --- | --- |
| Branch creation | Yes | `feat-{phase}`. |
| Implementation sessions | Yes | Fresh Codex sessions per step. |
| Step review | Yes | Separate review-only sessions. |
| Lint/build/test verification | Yes | Owned by review reports and CI/checks. |
| Phase evaluation | Yes | Rubric gate in `phases/{phase}/eval/phase-eval.json`. |
| Commit creation | Yes | Executor owns commits. |
| Push | Optional | `--push`, `--pr`, and `--merge`. |
| PR creation | Optional | `--pr` or `--merge`. |
| PR merge | Optional | `--merge`, only after checks pass. |
| Manual production deploy | No | Separate human approval. |
| Secrets/credentials | No | Separate human approval; never print raw values. |
| Destructive DB or history rewrite | No | Separate human approval; guards should block common cases. |
| External Scoreboard/Next-Prompt/Engineering Report finalization | No | Draft only unless human approves final write. |

## Project-specific adaptation

Target repositories should adapt `AGENTS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/ADR.md`, and phase-local docs to their stack. Keep the workflow boundary above stable unless the user explicitly changes the operating model for that project.
