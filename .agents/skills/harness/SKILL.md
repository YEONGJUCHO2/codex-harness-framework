---
name: harness
description: Use when setting up or using a portable Codex Harness workflow, creating or reviewing phase/step plans, editing phases/* files, or running scripts/execute.py.
---

# Harness Workflow

This repository uses a portable Harness workflow for Codex-driven app development. Use it to plan work as small independent steps, execute those steps in fresh Codex sessions, review each step with a separate review-only session, and keep project rules, architecture docs, tests, review reports, eval reports, and phase metadata in sync.

## Workflow

### A. Explore

Before proposing implementation work, read the project contract files that exist in the target repository:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- Any other `docs/*.md` directly relevant to the task

If the phase has local guardrails, also read:

- `phases/{phase}/AGENTS.md` or `phases/{phase}/Agent.md`
- `phases/{phase}/docs/*.md`

### B. Discuss

If the implementation needs product clarification, technical direction, credentials, production access, destructive data changes, or a safety-sensitive decision, present the decision point before creating phase files or editing implementation files. If the user gives a concrete task and explicitly authorizes execution through PR or merge, do not make them fill a large blank template or approve repeated cards; proceed within that boundary and stop only for the gated cases above.

### C. Design Steps

When the user asks for an implementation plan, draft the steps first and ask for feedback before writing phase files.

Step design rules:

1. **Minimize scope**: each step should cover one layer, module, or workflow slice.
2. **Make each step self-contained**: every `stepN.md` runs in an independent Codex implementation session. Do not rely on chat history.
3. **Force preparation**: list the docs, phase-local rules, and prior-step files the implementation session must read before editing.
4. **Specify interfaces, not full implementations**: provide function/class/module signatures and essential constraints. Leave implementation details to the executing session unless a specific algorithm is required.
5. **Do not put official verification commands in the implementation instructions**. Implementation agents may run targeted checks while debugging, but official verification is owned by the review agent.
6. **Write concrete warnings**: use "Do not do X. Reason: Y."
7. **Use sortable phase names**: prefer `01-login`, `02-auth-api`, `03-dashboard`.

### D. Create Files

After user approval, create or update these files.

#### `phases/index.json`

Top-level phase index. Append a new entry if the file already exists.

```json
{
  "phases": [
    {
      "dir": "01-login",
      "status": "pending"
    }
  ]
}
```

Rules:

- `dir`: phase directory name.
- `status`: one of `"pending"`, `"completed"`, `"error"`, `"blocked"`, `"review_failed"`.
- Do not add timestamps at creation time. `scripts/execute.py` records them while running.

#### `phases/{phase}/AGENTS.md`

Optional phase-local rules. Use this when a phase needs tighter constraints than the root `AGENTS.md`.

Rules:

- Root `AGENTS.md` remains the global contract and should stay under 300 lines.
- Phase `AGENTS.md` adds constraints for that phase only.
- If phase rules conflict with root CRITICAL rules, root CRITICAL rules win.
- Use phase docs for detailed domain notes; keep phase `AGENTS.md` focused.

#### `phases/{phase}/index.json`

Task-level index.

```json
{
  "project": "<project-name>",
  "phase": "01-login",
  "steps": [
    { "step": 0, "name": "login-form", "status": "pending" },
    { "step": 1, "name": "login-api", "status": "pending" }
  ]
}
```

Rules:

- `project`: project name from `AGENTS.md`, `package.json`, or the repository directory.
- `phase`: phase name and directory name.
- `steps[].step`: zero-based step number.
- `steps[].name`: kebab-case slug.
- `steps[].status`: initially `"pending"`.

Step statuses:

| Status | Meaning | Writer |
| --- | --- | --- |
| `pending` | Step has not produced reviewable work yet. | Plan author or executor |
| `in_progress` | Implementation session is currently working. | Executor |
| `ready_for_review` | Implementation is ready for independent review. | Implementation agent |
| `completed` | Review approved the step. | Executor only |
| `blocked` | User input, credentials, or manual setup is required. | Implementation/review agent, timestamp by executor |
| `error` | Implementation failed to produce reviewable work within its attempt budget. | Executor |
| `review_failed` | Review requested changes after the review-cycle budget was exhausted. | Executor |

Important:

- Implementation agents must never mark a step `completed`.
- `completed` is written only by `scripts/execute.py` after a review report with `decision: "approved"`.
- Implementation attempts and review cycles are separate budgets:
  - implementation attempts: max 3 per implementation pass
  - review cycles: max 3 per step

#### `phases/{phase}/steps/step{N}.md`

Preferred location for step files. The executor also supports legacy `phases/{phase}/step{N}.md` and `Step.{N}`.

````markdown
# Step {N}: {name}

## Read First

Read these files before editing:

- `/AGENTS.md`
- `/docs/PRD.md`
- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`
- `/phases/{phase}/AGENTS.md` when present
- {files created or changed by prior steps}

Read the prior-step code carefully before modifying it.

## Task

{Concrete implementation instructions. Include file paths, class/function signatures, behavior constraints, and data contracts. Keep snippets at interface/signature level unless exact implementation is required.}

## Submit For Review

When implementation is ready:

1. Update `phases/{phase}/index.json` for this step to `"status": "ready_for_review"`.
2. Add a concise `"summary"` describing changed files and key decisions.
3. Do not mark the step completed.

## Do Not

- Do not run broad official verification as a completion gate. Reason: the review agent owns official verification.
- Do not set `"status": "completed"`. Reason: only `scripts/execute.py` may complete a reviewed step.
- Do not break existing tests.
- Do not commit manually. `scripts/execute.py` owns commit creation.
````

### E. Execute

Run a planned task only when the user asks for execution.

```bash
python3 scripts/execute.py 01-login
python3 scripts/execute.py 01-login --push
python3 scripts/execute.py 01-login --pr
python3 scripts/execute.py 01-login --merge
```

Release modes:

- default: complete the phase locally.
- `--push`: push `feat-{phase}` after approved phase completion.
- `--pr`: push and create or reuse a GitHub PR.
- `--merge`: push, create or reuse a PR, wait for checks, and merge only when checks pass. Do not force-merge failing or conflicting PRs; skip merge when GitHub reports no checks.

Use `--pr` or `--merge` only when the user's command authorizes that boundary.

`execute.py` handles:

- Creating or checking out `feat-{phase}`.
- Injecting root `AGENTS.md`, root `docs/*.md`, phase `AGENTS.md`, and phase docs.
- Loading Codex hooks through `CODEX_PROJECT_DIR`, `CLAUDE_PROJECT_DIR`, git root, then `pwd` fallback.
- Running `npm run lint`, `npm run build`, and `npm run test` from the Stop hook when the target repository has `package.json`.
- Blocking high-risk shell commands through `.codex/hooks/deny-dangerous-command.sh`.
- Passing completed step summaries to later implementation and review sessions.
- Running implementation sessions until `ready_for_review`.
- Running strict review-only sessions for each step.
- Running `npm run lint`, `npm run test`, and `npm run build` from the review session.
- Retrying implementation failures up to 3 times.
- Handling review-requested changes as separate review cycles, not implementation failures.
- Separating code commits from phase metadata commits.
- Recording `created_at`, `started_at`, `completed_at`, `failed_at`, `blocked_at`, and `review_failed_at`.
- Running phase-level rubric evaluation after all steps are approved.
- Optional release follow-through with `--push`, `--pr`, or `--merge` after the phase evaluator approves.
- Preserving human gates for manual production deploys, credentials/secrets, destructive database work, git history rewrites, and final external durable records.

Generated runtime files:

```text
phases/{phase}/outputs/
phases/{phase}/reviews/
phases/{phase}/eval/
```

### F. Phase Evaluation

After every step is approved, `execute.py` runs a phase evaluation session. This is not just lint/test/build. The phase evaluator scores the increment with a rubric:

- correctness
- architecture compliance
- test quality
- maintainability
- security
- documentation drift
- UX and Lighthouse-style observations when applicable

Approval requires:

- `overallScore >= 85`
- no blocker findings
- no unresolved docs drift

The phase evaluator writes:

```text
phases/{phase}/eval/phase-eval.json
```

### Recovery

- For an `error` step, reset that step to `"pending"`, remove `error_message`, and rerun.
- For a `blocked` step, resolve `blocked_reason`, reset that step to `"pending"`, remove `blocked_reason`, and rerun.
- For a `review_failed` step, address the latest review report, reset status to `"pending"`, and rerun.
