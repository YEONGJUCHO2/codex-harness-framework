# Codex Harness Framework

Portable Harness setup for Codex-driven app development with separate implementation, review, and phase-evaluation loops.

This repository is a template. It intentionally does not include app implementation output or completed `phases/*` results.

## What To Copy

Copy these files into an app repository:

- `.gitignore`
- `.github/pull_request_template.md`
- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/HARNESS_WORKFLOW.md`
- `docs/UI_GUIDE.md` when the app has a frontend
- `.agents/skills/harness/SKILL.md`
- `.agents/skills/review/SKILL.md`
- `.codex/config.toml`
- `.codex/hooks.json`
- `.codex/hooks/deny-dangerous-command.sh`
- `.codex/hooks/stop-verification.sh`
- `.codex/hooks/tdd-guard.sh`
- `scripts/execute.py`
- `scripts/test_execute.py`
- `scripts/test_dangerous_command_guard.py`
- `scripts/test_stop_verification_hook.py`
- `scripts/test_tdd_guard.py`
- `requirements-dev.txt`

Then replace the placeholders in `AGENTS.md` and `docs/*.md` with the target app's real product, architecture, stack, and guardrails.

## Workflow

1. Ask Codex to use the Harness workflow and draft a phase plan.
2. Review the proposed steps before files are created.
3. Create `phases/index.json`, `phases/{phase}/index.json`, optional `phases/{phase}/AGENTS.md`, and `phases/{phase}/steps/stepN.md`.
4. Run:

```bash
python3 scripts/execute.py {task-name}
```

5. To push, open a PR, or merge after checks pass, run one of:

```bash
python3 scripts/execute.py {task-name} --push
python3 scripts/execute.py {task-name} --pr
python3 scripts/execute.py {task-name} --merge
```

Use `--merge` only when the user's command authorizes merge after checks pass. It pushes the branch, creates or reuses a GitHub PR, waits for checks with fail-fast behavior, and merges only when checks pass. It does not force-merge failing or conflicting PRs.

## Contracts

- Skills live in `.agents/skills`, matching the Codex live demo structure.
- Codex hooks are enabled by `.codex/config.toml`.
- Codex hook commands resolve the project root through `CODEX_PROJECT_DIR`, `CLAUDE_PROJECT_DIR`, git root, then `pwd`.
- The Stop hook runs `npm run lint`, `npm run build`, and `npm run test` when a copied target repository has `package.json`.
- The default hook is a TDD guard that blocks implementation edits when a matching test file does not exist.
- A dangerous-command guard blocks high-risk shell commands such as `rm -rf`, `git push --force`, `git reset --hard`, and `DROP TABLE`.
- Implementation sessions must submit work as `ready_for_review`, but must not mark steps `completed`.
- Review sessions run the official verification commands: `npm run lint`, `npm run build`, and `npm run test`.
- Review-requested changes consume review cycles, not implementation-attempt retries.
- `scripts/execute.py` is the only component that marks a step `completed`.
- `scripts/execute.py` injects root `AGENTS.md`, root `docs/*.md`, phase `AGENTS.md`, and phase docs when present.
- `scripts/execute.py` records implementation outputs, review reports, phase eval reports, timestamps, and commits.
- `scripts/execute.py --pr` pushes the phase branch and creates or reuses a GitHub PR.
- `scripts/execute.py --merge` waits for PR checks and merges only when checks pass; it must not force-merge failing or conflicting PRs.
- Manual production deploys, credentials/secrets, destructive database operations, git history rewrites, and final external durable records remain human-gated.
- Root `AGENTS.md` should stay under 300 lines. Put detailed rules in `docs/` or phase-local `AGENTS.md`.

## Phase Layout

Preferred layout:

```text
phases/
  index.json
  01-login/
    AGENTS.md
    index.json
    steps/
      step0.md
      step1.md
    outputs/
    reviews/
    eval/
```

`outputs/`, `reviews/`, and `eval/` are created by `scripts/execute.py`.

## Completion Gates

Each step uses two separate loops:

- Implementation loop: up to 3 attempts to produce `ready_for_review`.
- Review loop: up to 3 review cycles. The review-only session runs lint/build/test and writes a JSON report.

After every step is approved, the phase evaluator writes `phases/{phase}/eval/phase-eval.json` with rubric scores. Phase completion requires approval from this eval gate.

## Validation

Framework tests are Python tests:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest scripts/test_execute.py scripts/test_tdd_guard.py scripts/test_dangerous_command_guard.py scripts/test_stop_verification_hook.py -q
```

These tests validate the Harness executor, PR/merge orchestration, and Codex hooks, not the target app's own test suite.
