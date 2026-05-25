---
name: harness
description: Use when setting up or using a portable Codex Harness workflow, creating or reviewing phase/step plans, editing phases/* files, or running scripts/execute.py.
---

# Harness Workflow

This repository uses a portable Harness workflow for Codex-driven app development. Use it to plan work as small independent steps, execute those steps in fresh Codex sessions, and keep project rules, architecture docs, tests, and phase metadata in sync.

## Workflow

### A. Explore

Before proposing implementation work, read the project contract files that exist in the target repository:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- Any other `docs/*.md` directly relevant to the task

Use sub-agents only when the user explicitly asks for delegated or parallel agent work.

### B. Discuss

If the implementation needs product clarification or a technical decision, present the decision point before creating phase files or editing implementation files.

### C. Design Steps

When the user asks for an implementation plan, draft the steps first and ask for feedback before writing phase files.

Step design rules:

1. **Minimize scope**: each step should cover one layer, module, or workflow slice.
2. **Make each step self-contained**: every `stepN.md` runs in an independent Codex session. Do not rely on chat history.
3. **Force preparation**: list the docs and prior-step files the session must read before editing.
4. **Specify interfaces, not full implementations**: provide function/class/module signatures and essential constraints. Leave implementation details to the executing session unless a specific algorithm is required.
5. **Use executable acceptance criteria**: prefer commands such as `npm run lint`, `npm run test`, and `npm run build`.
6. **Write concrete warnings**: use "Do not do X. Reason: Y."
7. **Use kebab-case names**: examples are `project-setup`, `core-domain`, `api-layer`, `client-flow`.

### D. Create Files

After user approval, create or update these files.

#### `phases/index.json`

Top-level phase index. Append a new entry if the file already exists.

```json
{
  "phases": [
    {
      "dir": "0-mvp",
      "status": "pending"
    }
  ]
}
```

Rules:

- `dir`: task directory name.
- `status`: one of `"pending"`, `"completed"`, `"error"`, `"blocked"`.
- Do not add timestamps at creation time. `scripts/execute.py` records them while running.

#### `phases/{task-name}/index.json`

Task-level index.

```json
{
  "project": "<project-name>",
  "phase": "<task-name>",
  "steps": [
    { "step": 0, "name": "project-setup", "status": "pending" },
    { "step": 1, "name": "core-domain", "status": "pending" },
    { "step": 2, "name": "api-layer", "status": "pending" }
  ]
}
```

Rules:

- `project`: project name from `AGENTS.md`, `package.json`, or the repository directory.
- `phase`: task name and directory name.
- `steps[].step`: zero-based step number.
- `steps[].name`: kebab-case slug.
- `steps[].status`: initially `"pending"`.

Status fields:

| Transition | Fields | Writer |
| --- | --- | --- |
| to `completed` | `completed_at`, `summary` | Codex writes `summary`; `execute.py` writes timestamp |
| to `error` | `failed_at`, `error_message` | Codex writes message; `execute.py` writes timestamp |
| to `blocked` | `blocked_at`, `blocked_reason` | Codex writes reason; `execute.py` writes timestamp |

The `summary` must be a useful one-line description for later steps. Include changed files and key decisions when relevant.

Do not manually add task-level `created_at` or step-level `started_at`; `execute.py` records them.

#### `phases/{task-name}/step{N}.md`

Create one Markdown file per step.

````markdown
# Step {N}: {name}

## Read First

Read these files before editing:

- `/AGENTS.md`
- `/docs/PRD.md`
- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`
- {files created or changed by prior steps}

Read the prior-step code carefully before modifying it.

## Task

{Concrete implementation instructions. Include file paths, class/function signatures, behavior constraints, and data contracts. Keep snippets at interface/signature level unless exact implementation is required.}

## Acceptance Criteria

```bash
npm run lint
npm run test
npm run build
```

## Verification

1. Run the acceptance criteria commands.
2. Check the architecture guardrails:
   - Does the work match `PRD.md` scope?
   - Does the directory layout follow `ARCHITECTURE.md`?
   - Does the stack stay within `ADR.md`?
   - Does it avoid violating `AGENTS.md` CRITICAL rules?
3. Update `phases/{task-name}/index.json` for this step:
   - Success: set `"status": "completed"` and add `"summary": "one-line output summary"`.
   - Failed after 3 self-correction attempts: set `"status": "error"` and add `"error_message": "specific error"`.
   - Needs user input: set `"status": "blocked"` and add `"blocked_reason": "specific reason"`, then stop.

## Do Not

- {Concrete forbidden action. Format: "Do not do X. Reason: Y."}
- Do not break existing tests.
- Do not commit manually. `scripts/execute.py` owns commit creation.
````

### E. Execute

Run a planned task only when the user asks for execution.

```bash
python3 scripts/execute.py {task-name}
python3 scripts/execute.py {task-name} --push
```

`execute.py` handles:

- Creating or checking out `feat-{task-name}`.
- Injecting `AGENTS.md` and `docs/*.md` guardrails.
- Passing completed step summaries to later steps.
- Retrying failed steps up to 3 times with the previous error message.
- Separating code commits from phase metadata commits.
- Recording `created_at`, `started_at`, `completed_at`, `failed_at`, and `blocked_at`.

Recovery:

- For an `error` step, reset that step to `"pending"`, remove `error_message`, and rerun.
- For a `blocked` step, resolve `blocked_reason`, reset that step to `"pending"`, remove `blocked_reason`, and rerun.
