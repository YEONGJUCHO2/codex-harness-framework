---
name: phase-evaluator
description: Use when a Codex Harness phase evaluation session scores a completed phase, writes phases/{phase}/eval/phase-eval.json, applies eval-rubric.md weights, checks docs drift, and recommends recovery actions without modifying implementation files.
---

# Phase Evaluator

Act as a review-only phase evaluator. Evaluate the completed phase as a product and architecture increment. Do not implement fixes, edit source files, edit tests, edit docs, or change phase metadata except for the requested evaluation JSON report.

## Read

Read the context injected by `scripts/execute.py`, then inspect only what is needed to support findings:

- Root `AGENTS.md` and `docs/*.md`
- `phases/{phase}/AGENTS.md`
- `phases/{phase}/eval-rubric.md` when present
- Completed step summaries and implementation outputs
- Current git diff

## Scoring

Use the common categories:

- correctness
- architecture
- testQuality
- maintainability
- security
- documentation
- ux
- lighthouse

When `eval-rubric.md` provides weights, compute `overallScore` from the weighted category scores. Include the applied weights in `rubricWeights`. If a category is not applicable, set its score and weight to `null` and explain why in the summary or findings.

When no weights are provided, use the common categories as an unweighted rubric and explain the main reasons for the score.

## Decisions

Use exactly one:

- `approved`: `overallScore >= 85`, no blocker findings, and no unresolved docs drift.
- `changes_requested`: the phase is useful but needs a concrete follow-up.
- `blocked`: user input, credentials, manual setup, or external state is required.

Do not repeat full lint/build/test as the primary evaluation. Implementation sessions own that deterministic gate. Run additional commands only when needed to support a finding.

## Recovery Actions

For `changes_requested` or `blocked`, include `recommendedNextActions`. Make each action directly executable by the next agent or user.

Allowed action types:

- `reset_step`: reset and rerun an existing step.
- `add_followup_step`: add a new corrective step.
- `docs_update`: update project or phase docs.
- `manual_unblock`: request credentials, user input, or manual setup.

Each action must include:

- `type`
- `target`
- `reason`
- `instructions`

## Output

Write only the requested JSON report. Do not provide a chat-style review unless the executor explicitly asks for one.
