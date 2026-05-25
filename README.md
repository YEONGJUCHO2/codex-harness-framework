# Codex Harness Framework

Portable Harness setup for Codex-driven app development.

This repository is a template. It intentionally does not include app implementation output or completed `phases/*` results.

## What To Copy

Copy these files into an app repository:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/UI_GUIDE.md` when the app has a frontend
- `.agents/skills/harness/SKILL.md`
- `.agents/skills/review/SKILL.md`
- `.codex/config.toml`
- `.codex/hooks.json`
- `.codex/hooks/tdd-guard.sh`
- `scripts/execute.py`
- `scripts/test_execute.py`
- `scripts/test_tdd_guard.py`

Then replace the placeholders in `AGENTS.md` and `docs/*.md` with the target app's real product, architecture, stack, and guardrails.

## Workflow

1. Ask Codex to use the Harness workflow and draft a phase plan.
2. Review the proposed steps before files are created.
3. Create `phases/index.json`, `phases/{task}/index.json`, and `phases/{task}/stepN.md`.
4. Run:

```bash
python3 scripts/execute.py {task-name}
```

Use `--push` only when the phase branch should be pushed after completion.

## Contracts

- Skills live in `.agents/skills`, matching the Codex live demo structure.
- Codex hooks are enabled by `.codex/config.toml`.
- The default hook is a TDD guard that blocks implementation edits when a matching test file does not exist.
- Step sessions must update phase metadata, but must not commit manually. `scripts/execute.py` owns commit creation.
- `scripts/execute.py` injects `AGENTS.md` and `docs/*.md`, runs each pending step with `codex exec`, retries failed steps up to three times, and records timestamps.

## Validation

Framework tests are Python tests:

```bash
PYTHONPATH=/tmp/harness_pytest python3 -m pytest scripts/test_execute.py scripts/test_tdd_guard.py -q
```

Install `pytest` in a project-local environment, or use a temporary target path as shown in development sessions.
