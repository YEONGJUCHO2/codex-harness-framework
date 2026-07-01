---
name: harness
description: Use when setting up or using a portable Codex Harness workflow, creating or reviewing phase/step plans, editing phases/* files, or running scripts/execute.py.
---

# Harness Workflow

This repository uses a portable Harness workflow for Codex-driven app development. Use it to plan work as small independent steps, execute those steps in fresh Codex implementation sessions, keep lint/build/test verification inside the implementation session, and keep project rules, architecture docs, tests, eval reports, and phase metadata in sync.

## Workflow

### A. Explore

Before proposing implementation work, read the project contract files that exist in the target repository:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- Any other `docs/*.md` directly relevant to the task

If the phase has local guardrails, also read:

- `phases/{phase}/AGENTS.md`
- `phases/{phase}/docs/*.md`

### B. Discuss

If the implementation needs product clarification or a technical decision, present the decision point before creating phase files or editing implementation files.

### C. Design Steps

When the user asks for an implementation plan, draft the steps first and ask for feedback before writing phase files.

Step design rules:

1. **Minimize scope**: each step should cover one layer, module, or workflow slice.
2. **Make each step self-contained**: every `stepN.md` runs in an independent Codex implementation session. Do not rely on chat history.
3. **Force preparation**: list the docs, phase-local rules, and prior-step files the implementation session must read before editing.
4. **Specify interfaces, not full implementations**: provide function/class/module signatures and essential constraints. Leave implementation details to the executing session unless a specific algorithm is required.
5. **Include official verification commands in the implementation contract**. Implementation agents own deterministic lint/build/test verification before submitting completion.
6. **Create phase-local rules**: every phase must include `phases/{phase}/AGENTS.md`, even when it only states that the root rules apply without overrides.
7. **Create phase-specific evaluation guidance**: every phase should include `phases/{phase}/eval-rubric.md` that adapts and weights the common rubric for the phase scope.
8. **Write concrete warnings**: use "Do not do X. Reason: Y."
9. **Use sortable phase names**: prefer `01-login`, `02-auth-api`, `03-dashboard`.

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
- `status`: one of `"pending"`, `"completed"`, `"error"`, `"blocked"`, `"evaluation_failed"`.
- Do not add timestamps at creation time. `scripts/execute.py` records them while running.

#### `phases/{phase}/AGENTS.md`

Required phase-local rules. Create this for every phase so each independent Codex session has a phase-specific contract.

Rules:

- Root `AGENTS.md` remains the global contract and should stay under 300 lines.
- Phase `AGENTS.md` adds constraints for that phase only.
- If phase rules conflict with root CRITICAL rules, root CRITICAL rules win.
- Use phase docs for detailed domain notes; keep phase `AGENTS.md` focused.
- If no extra rules are needed, explicitly say that the phase inherits root rules without overrides.

Template:

```markdown
# Phase Rules: {phase}

## Scope
- {one-line phase scope}

## Additional Rules
- Inherit root `/AGENTS.md` CRITICAL rules.
- {phase-specific constraint, or "No additional phase-specific constraints."}

## Verification
- Implementation sessions must run the commands named in each step before setting `ready_for_completion`.
```

#### `phases/{phase}/eval-rubric.md`

Required phase-specific evaluation guidance. Use this to adapt and weight the common rubric for the phase scope. Keep it short enough for the evaluator to apply consistently.

Template:

```markdown
# Evaluation Rubric: {phase}

## Phase Goal
{What this phase must accomplish from the user's point of view.}

## Weights
- Correctness: 30
- Architecture: 15
- Test Quality: 20
- Maintainability: 10
- Security: 10
- Documentation: 10
- UX: 5
- Lighthouse: 0

## Category Guidance
- Correctness: {phase-specific expectations}
- Architecture: {boundaries and integration rules that matter here}
- Test Quality: {what meaningful coverage means for this phase}
- Maintainability: {complexity, duplication, or naming concerns}
- Security: {auth, data, privacy, or command-safety concerns}
- Documentation: {docs or phase notes that must stay aligned}
- UX: {only if user-facing UI changed; otherwise mark not applicable}
- Lighthouse: {only if frontend performance is relevant; otherwise mark not applicable}

## Approval Notes
- Name any phase-specific blocker conditions.
```

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
| `pending` | Step has not produced verified work yet. | Plan author or executor |
| `in_progress` | Implementation session is currently working. | Executor |
| `ready_for_completion` | Implementation and verification are done. | Implementation agent |
| `completed` | Executor accepted the verified step and recorded metadata. | Executor only |
| `blocked` | User input, credentials, or manual setup is required. | Implementation agent or phase evaluator, timestamp by executor |
| `error` | Implementation failed to produce verified work within its attempt budget. | Executor |
| `evaluation_failed` | Phase evaluation requested changes after all steps completed. | Executor |

Important:

- Implementation agents must never mark a step `completed`.
- `completed` is written only by `scripts/execute.py` after the implementation session reports `ready_for_completion`.
- Implementation attempts are capped at 3 per step.

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
- `/phases/{phase}/AGENTS.md`
- `/phases/{phase}/eval-rubric.md`
- {files created or changed by prior steps}

Read the prior-step code carefully before modifying it.

## Task

{Concrete implementation instructions. Include file paths, class/function signatures, behavior constraints, and data contracts. Keep snippets at interface/signature level unless exact implementation is required.}

## Submit For Completion

When implementation is ready:

1. Run the official verification commands (`npm run lint`, `npm run build`, `npm run test`) or the step-specific AC commands when different.
2. Update `phases/{phase}/index.json` for this step to `"status": "ready_for_completion"`.
3. Add a concise `"summary"` describing changed files, key decisions, and verification results.
4. Do not mark the step completed.

## Do Not

- Do not skip official verification. Reason: the implementation session owns deterministic lint/build/test.
- Do not set `"status": "completed"`. Reason: only `scripts/execute.py` may complete a verified step.
- Do not break existing tests.
- Do not commit manually. `scripts/execute.py` owns commit creation.
````

### E. Execute

Run a planned task only when the user asks for execution.

```bash
python3 scripts/execute.py 01-login
python3 scripts/execute.py 01-login --push
```

`execute.py` handles:

- Creating or checking out `feat-{phase}`.
- Injecting root `AGENTS.md`, root `docs/*.md`, phase `AGENTS.md`, and phase docs.
- Loading Codex hooks through `CODEX_PROJECT_DIR`, `CLAUDE_PROJECT_DIR`, git root, then `pwd` fallback.
- Running `npm run lint`, `npm run build`, and `npm run test` from the Stop hook when the target repository has `package.json`.
- Blocking high-risk shell commands through `.codex/hooks/deny-dangerous-command.sh`.
- Passing completed step summaries to later implementation sessions.
- Running implementation sessions until `ready_for_completion`.
- Retrying implementation failures up to 3 times.
- Separating code commits from phase metadata commits.
- Recording `created_at`, `started_at`, `completed_at`, `failed_at`, `blocked_at`, and `evaluation_failed_at`.
- Running phase-level rubric evaluation after all steps are completed, using `.agents/skills/phase-evaluator/SKILL.md` and `phases/{phase}/eval-rubric.md` when present.

Generated runtime files:

```text
phases/{phase}/outputs/
phases/{phase}/eval/
```

### F. Phase Evaluation

After every step is completed, `execute.py` runs a phase evaluation session. This is not just lint/test/build. The phase evaluator follows `.agents/skills/phase-evaluator/SKILL.md` and scores the increment with the common rubric, interpreted through `phases/{phase}/eval-rubric.md` when present:

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

For `changes_requested` or `blocked`, the evaluator should include `recommendedNextActions` so the next run knows whether to reset a step, add a follow-up step, update docs, or wait for manual unblock.

### Recovery

- For an `error` step, reset that step to `"pending"`, remove `error_message`, and rerun.
- For a `blocked` step, resolve `blocked_reason`, reset that step to `"pending"`, remove `blocked_reason`, and rerun.
- For an `evaluation_failed` phase, address the latest phase eval report, reset the relevant follow-up step or phase status to `"pending"`, and rerun.
