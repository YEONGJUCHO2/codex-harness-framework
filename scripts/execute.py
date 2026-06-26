#!/usr/bin/env python3
"""
Harness Step Executor.

Runs phase steps through separate implementation and review Codex sessions.
Implementation sessions may only prepare work for review. The executor marks a
step completed only after a dedicated review session approves it.
"""

import argparse
import contextlib
import json
import subprocess
import sys
import threading
import time
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def progress_indicator(label: str):
    """Terminal progress indicator. The yielded object exposes elapsed seconds."""
    frames = "|/-\\"
    stop = threading.Event()
    t0 = time.monotonic()

    def _animate():
        idx = 0
        while not stop.wait(0.12):
            sec = int(time.monotonic() - t0)
            sys.stderr.write(f"\r{frames[idx % len(frames)]} {label} [{sec}s]")
            sys.stderr.flush()
            idx += 1
        sys.stderr.write("\r" + " " * (len(label) + 20) + "\r")
        sys.stderr.flush()

    th = threading.Thread(target=_animate, daemon=True)
    th.start()
    info = types.SimpleNamespace(elapsed=0.0)
    try:
        yield info
    finally:
        stop.set()
        th.join()
        info.elapsed = time.monotonic() - t0


class StepExecutor:
    """Executes phase steps with separate implementation, review, and eval gates."""

    MAX_IMPLEMENTATION_ATTEMPTS = 3
    MAX_REVIEW_CYCLES = 3
    MAX_RETRIES = MAX_IMPLEMENTATION_ATTEMPTS  # Backward-compatible name.

    FEAT_MSG = "feat({phase}): step {num} - {name}"
    CHORE_MSG = "chore({phase}): step {num} output"
    TZ = timezone(timedelta(hours=9))

    STEP_BLOCKING_STATUSES = {"error", "blocked", "review_failed"}
    REVIEW_DECISIONS = {"approved", "changes_requested", "blocked"}

    def __init__(self, phase_dir_name: str, *, auto_push: bool = False):
        self._root = str(ROOT)
        self._phases_dir = ROOT / "phases"
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._auto_push = auto_push

        if not self._phase_dir.is_dir():
            print(f"ERROR: {self._phase_dir} not found")
            sys.exit(1)

        self._index_file = self._phase_dir / "index.json"
        if not self._index_file.exists():
            print(f"ERROR: {self._index_file} not found")
            sys.exit(1)

        idx = self._read_json(self._index_file)
        self._project = idx.get("project", "project")
        self._phase_name = idx.get("phase", phase_dir_name)
        self._total = len(idx["steps"])
        self._outputs_dir = self._phase_dir / "outputs"
        self._reviews_dir = self._phase_dir / "reviews"
        self._eval_dir = self._phase_dir / "eval"

    def run(self):
        self._print_header()
        self._check_blockers()
        self._checkout_branch()
        self._ensure_runtime_dirs()
        guardrails = self._load_guardrails()
        self._ensure_created_at()
        self._execute_all_steps(guardrails)
        self._run_phase_eval(guardrails)
        self._finalize()

    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    @staticmethod
    def _read_json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _ensure_runtime_dirs(self):
        self._outputs_dir.mkdir(parents=True, exist_ok=True)
        self._reviews_dir.mkdir(parents=True, exist_ok=True)
        self._eval_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _step_record(index: dict, step_num: int) -> dict:
        for step in index["steps"]:
            if step["step"] == step_num:
                return step
        raise KeyError(f"step {step_num} not found")

    def _relative(self, path: Path) -> str:
        try:
            return path.relative_to(ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

    def _checkout_branch(self):
        branch = f"feat-{self._phase_name}"

        r = self._run_git("rev-parse", "--git-dir")
        if r.returncode != 0:
            print("  ERROR: git is unavailable or this is not a git repository.")
            print(f"  {r.stderr.strip()}")
            sys.exit(1)

        r = self._run_git("symbolic-ref", "--quiet", "--short", "HEAD")
        current_branch = r.stdout.strip() if r.returncode == 0 else ""
        if current_branch == branch:
            return

        r = self._run_git("rev-parse", "--verify", branch)
        r = self._run_git("checkout", branch) if r.returncode == 0 else self._run_git("checkout", "-b", branch)
        if r.returncode != 0:
            print(f"  ERROR: failed to checkout branch '{branch}'.")
            print(f"  {r.stderr.strip()}")
            print("  Hint: stash or commit current changes, then retry.")
            sys.exit(1)

        print(f"  Branch: {branch}")

    def _unstage_phase_metadata(self, has_head: bool):
        phase_rel = f"phases/{self._phase_dir_name}"
        index_rel = f"phases/{self._phase_dir_name}/index.json"
        legacy_output_rels = [
            f"phases/{self._phase_dir_name}/step{s['step']}-output.json"
            for s in self._read_json(self._index_file)["steps"]
        ]

        if has_head:
            self._run_git("reset", "HEAD", "--", phase_rel)
            self._run_git("reset", "HEAD", "--", index_rel)
            for rel in legacy_output_rels:
                self._run_git("reset", "HEAD", "--", rel)
        else:
            self._run_git("rm", "-r", "--cached", "--ignore-unmatch", "--", phase_rel)
            self._run_git("rm", "--cached", "--ignore-unmatch", "--", index_rel)
            for rel in legacy_output_rels:
                self._run_git("rm", "--cached", "--ignore-unmatch", "--", rel)

    def _commit_step(self, step_num: int, step_name: str):
        has_head = self._run_git("rev-parse", "--verify", "HEAD").returncode == 0

        self._run_git("add", "-A")
        self._unstage_phase_metadata(has_head)

        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name)
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  Commit: {msg}")
            else:
                print(f"  WARN: code commit failed: {r.stderr.strip()}")

        self._commit_housekeeping(self.CHORE_MSG.format(phase=self._phase_name, num=step_num))

    def _commit_housekeeping(self, message: str):
        phase_rel = f"phases/{self._phase_dir_name}"
        self._run_git("add", "-A", "--", phase_rel)
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            r = self._run_git("commit", "-m", message)
            if r.returncode != 0:
                print(f"  WARN: housekeeping commit failed: {r.stderr.strip()}")

    def _update_top_index(self, status: str):
        if not self._top_index_file.exists():
            return
        top = self._read_json(self._top_index_file)
        ts_key = {
            "completed": "completed_at",
            "error": "failed_at",
            "blocked": "blocked_at",
            "review_failed": "review_failed_at",
        }.get(status)
        for phase in top.get("phases", []):
            if phase.get("dir") == self._phase_dir_name:
                phase["status"] = status
                if ts_key:
                    phase[ts_key] = self._stamp()
                break
        self._write_json(self._top_index_file, top)

    def _load_guardrails(self) -> str:
        sections = []

        agents_md = ROOT / "AGENTS.md"
        if agents_md.exists():
            sections.append(f"## Root Rules (AGENTS.md)\n\n{agents_md.read_text(encoding='utf-8')}")

        docs_dir = ROOT / "docs"
        if docs_dir.is_dir():
            for doc in sorted(docs_dir.glob("*.md")):
                sections.append(f"## Root Doc: {doc.stem}\n\n{doc.read_text(encoding='utf-8')}")

        phase_dir = getattr(self, "_phase_dir", None)
        if phase_dir:
            for phase_agent in (phase_dir / "AGENTS.md", phase_dir / "Agent.md"):
                if phase_agent.exists():
                    sections.append(
                        f"## Phase Rules ({self._relative(phase_agent)})\n\n"
                        f"{phase_agent.read_text(encoding='utf-8')}"
                    )

            phase_docs_dir = phase_dir / "docs"
            if phase_docs_dir.is_dir():
                for doc in sorted(phase_docs_dir.glob("*.md")):
                    sections.append(f"## Phase Doc: {doc.stem}\n\n{doc.read_text(encoding='utf-8')}")

        return "\n\n---\n\n".join(sections) if sections else ""

    @staticmethod
    def _build_step_context(index: dict) -> str:
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in index["steps"]
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물 / Previous Step Outputs\n\n" + "\n".join(lines) + "\n\n"

    def _step_file(self, step_num: int) -> Path:
        candidates = [
            self._phase_dir / "steps" / f"step{step_num}.md",
            self._phase_dir / "steps" / f"Step.{step_num}.md",
            self._phase_dir / "steps" / f"Step.{step_num}",
            self._phase_dir / f"step{step_num}.md",
            self._phase_dir / f"Step.{step_num}.md",
            self._phase_dir / f"Step.{step_num}",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        print(f"  ERROR: step {step_num} file not found in {self._phase_dir}")
        sys.exit(1)

    def _build_preamble(self, guardrails: str, step_context: str, prev_error: Optional[str] = None) -> str:
        return self._build_implementation_preamble(
            guardrails=guardrails,
            step_context=step_context,
            prev_error=prev_error,
            review_feedback=None,
        )

    def _build_implementation_preamble(
        self,
        *,
        guardrails: str,
        step_context: str,
        prev_error: Optional[str],
        review_feedback: Optional[dict],
    ) -> str:
        retry_section = ""
        if prev_error:
            retry_section = f"\n## 이전 시도 실패 / Previous Implementation Attempt Failed\n\n{prev_error}\n\n---\n\n"

        review_section = ""
        if review_feedback:
            review_section = (
                "\n## Reviewer Requested Changes\n\n"
                f"{json.dumps(review_feedback, indent=2, ensure_ascii=False)}\n\n"
                "Address only these review findings, then submit for review again.\n\n---\n\n"
            )

        return (
            f"You are the implementation agent for {self._project}.\n"
            "Implement the requested step, then submit it for independent review.\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}{retry_section}{review_section}"
            "## 작업 규칙 / Implementation Rules\n\n"
            "1. Perform only the work requested by this step.\n"
            "2. Add or update tests required by the implementation.\n"
            "3. You may run targeted checks while debugging, but official AC lint/build/test verification is performed by the review agent.\n"
            "4. Do not set this step to completed. Only scripts/execute.py may set completed.\n"
            f"5. Update /phases/{self._phase_dir_name}/index.json for this step:\n"
            "   - Ready for review: set \"status\": \"ready_for_review\" and add a concise \"summary\".\n"
            "   - Needs user input: set \"status\": \"blocked\" and add \"blocked_reason\".\n"
            "   - Cannot produce reviewable work after self-correction: set \"status\": \"error\" and add \"error_message\".\n"
            "6. 커밋하지 마라. Do not commit. execute.py가 커밋을 담당하며 scripts/execute.py owns commit creation.\n\n---\n\n"
        )

    def _build_review_prompt(
        self,
        *,
        guardrails: str,
        step_context: str,
        step: dict,
        cycle: int,
        report_path: Path,
    ) -> str:
        step_num, step_name = step["step"], step["name"]
        step_file = self._step_file(step_num)
        report_rel = self._relative(report_path)
        schema = {
            "step": step_num,
            "name": step_name,
            "cycle": cycle,
            "decision": "approved | changes_requested | blocked",
            "summary": "short review summary",
            "commands": [
                {"cmd": "npm run lint", "exitCode": 0, "summary": "result"},
                {"cmd": "npm run build", "exitCode": 0, "summary": "result"},
                {"cmd": "npm run test", "exitCode": 0, "summary": "result"},
            ],
            "findings": [
                {
                    "severity": "blocker | major | minor",
                    "file": "path",
                    "line": 1,
                    "message": "specific issue",
                }
            ],
            "required_changes": ["actionable change request"],
        }

        return (
            "You are a strict review-only subagent. Be skeptical, concrete, and evidence-driven.\n"
            "Your job is to verify the implementation, not to fix it.\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}"
            f"## Step Under Review\n\nStep {step_num}: {step_name}\n\n"
            f"{step_file.read_text(encoding='utf-8')}\n\n---\n\n"
            "## Verification Commands\n\nRun:\n\n"
            "```bash\nnpm run lint\nnpm run build\nnpm run test\n```\n\n"
            "## Review Scope\n\n"
            "- Inspect the current git diff for this step.\n"
            "- Check requirement compliance against the step task and PRD.\n"
            "- Check architecture and ADR compliance.\n"
            "- Check AGENTS.md CRITICAL rules.\n"
            "- Check whether tests are meaningful, not merely present.\n"
            "- Do not modify implementation code, tests, or docs. You may only write the review JSON report.\n\n"
            "## Decision Rules\n\n"
            "- If any verification command fails, set decision to \"changes_requested\" unless the failure is caused by missing user input or external credentials.\n"
            "- If user input, credentials, or manual setup is required, set decision to \"blocked\".\n"
            "- Approve only when commands pass and the implementation satisfies the step, guardrails, and test-quality expectations.\n"
            f"- Write the JSON report to /{report_rel} using this schema:\n\n"
            "```json\n"
            f"{json.dumps(schema, indent=2, ensure_ascii=False)}\n"
            "```\n"
        )

    def _build_phase_eval_prompt(self, *, guardrails: str, report_path: Path) -> str:
        report_rel = self._relative(report_path)
        index = self._read_json(self._index_file)
        summary = self._build_step_context(index)
        schema = {
            "phase": self._phase_name,
            "decision": "approved | changes_requested | blocked",
            "overallScore": 0,
            "rubric": {
                "correctness": 0,
                "architecture": 0,
                "testQuality": 0,
                "maintainability": 0,
                "security": 0,
                "documentation": 0,
                "ux": None,
                "lighthouse": None,
            },
            "findings": [
                {
                    "severity": "blocker | major | minor",
                    "area": "correctness | architecture | docs | tests | security | ux",
                    "message": "specific issue",
                }
            ],
            "docsDrift": {
                "requiresUpdate": False,
                "targets": ["docs/ARCHITECTURE.md", "docs/ADR.md", "AGENTS.md"],
                "notes": "Root AGENTS.md should remain under 300 lines; move detail to docs or phase AGENTS.md.",
            },
            "summary": "short phase evaluation summary",
        }

        return (
            "You are the phase evaluation subagent. Evaluate the completed phase as a product and architecture increment.\n"
            "This is not a code-fixing task. Do not modify implementation files.\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{summary}"
            "## Evaluation Rules\n\n"
            "- Review the completed step summaries, review reports, and current git diff.\n"
            "- Score the phase with the rubric below on a 0-100 scale.\n"
            "- Do not repeat full lint/build/test as the primary evaluation; step reviewers already own that gate.\n"
            "- You may run additional checks only when needed to support a finding.\n"
            "- If this is a frontend phase and the app can be run, include Lighthouse-style UX/performance observations when practical.\n"
            "- Treat unresolved docs drift as changes_requested.\n"
            "- Keep root AGENTS.md focused and under 300 lines; detailed rules belong in docs or phase AGENTS.md.\n"
            "- Write only the phase evaluation JSON report.\n\n"
            "## Approval Threshold\n\n"
            "- decision approved requires overallScore >= 85, no blocker findings, and no required docs drift.\n"
            "- decision changes_requested means the phase is useful but needs follow-up before completion.\n"
            "- decision blocked means external user input, credentials, or manual setup is required.\n\n"
            f"Write the JSON report to /{report_rel} using this schema:\n\n"
            "```json\n"
            f"{json.dumps(schema, indent=2, ensure_ascii=False)}\n"
            "```\n"
        )

    def _invoke_codex(
        self,
        step: dict,
        preamble: str,
        *,
        output_path: Optional[Path] = None,
        prompt_body: Optional[str] = None,
        label: str = "implementation",
    ) -> dict:
        step_num, step_name = step["step"], step["name"]
        if prompt_body is None:
            step_file = self._step_file(step_num)
            prompt = preamble + step_file.read_text(encoding="utf-8")
        else:
            prompt = preamble + prompt_body

        result = subprocess.run(
            [
                "codex",
                "exec",
                "--json",
                "--sandbox",
                "danger-full-access",
                "-c",
                'approval_policy="never"',
                "--cd",
                self._root,
                prompt,
            ],
            cwd=self._root,
            capture_output=True,
            text=True,
            timeout=1800,
        )

        if result.returncode != 0:
            print(f"\n  WARN: Codex exited with code {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")

        output = {
            "step": step_num,
            "name": step_name,
            "label": label,
            "exitCode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if output_path is None:
            output_path = self._phase_dir / f"step{step_num}-output.json"
        self._write_json(output_path, output)
        return output

    def _print_header(self):
        print(f"\n{'=' * 60}")
        print("  Harness Step Executor")
        print(f"  Phase: {self._phase_name} | Steps: {self._total}")
        print(f"  Implementation attempts: {self.MAX_IMPLEMENTATION_ATTEMPTS}")
        print(f"  Review cycles: {self.MAX_REVIEW_CYCLES}")
        if self._auto_push:
            print("  Auto-push: enabled")
        print(f"{'=' * 60}")

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        for s in reversed(index["steps"]):
            status = s.get("status", "pending")
            if status == "error":
                print(f"\n  x Step {s['step']} ({s['name']}) failed.")
                print(f"  Error: {s.get('error_message', 'unknown')}")
                print("  Fix and reset status to 'pending' to retry.")
                sys.exit(1)
            if status == "review_failed":
                print(f"\n  x Step {s['step']} ({s['name']}) failed review.")
                print(f"  Review: {s.get('review_summary', 'unknown')}")
                print("  Address the review and reset status to 'pending' to retry.")
                sys.exit(1)
            if status == "blocked":
                print(f"\n  ! Step {s['step']} ({s['name']}) blocked.")
                print(f"  Reason: {s.get('blocked_reason', 'unknown')}")
                print("  Resolve and reset status to 'pending' to retry.")
                sys.exit(2)
            if status != "pending":
                break

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    def _read_decision_report(self, path: Path, *, fallback_step: dict, cycle: int) -> dict:
        if not path.exists():
            return {
                "step": fallback_step["step"],
                "name": fallback_step["name"],
                "cycle": cycle,
                "decision": "changes_requested",
                "summary": f"Review report was not created at {self._relative(path)}.",
                "commands": [],
                "findings": [
                    {
                        "severity": "blocker",
                        "file": self._relative(path),
                        "line": None,
                        "message": "Review agent did not produce the required JSON report.",
                    }
                ],
                "required_changes": ["Produce the required review report and rerun verification."],
            }

        try:
            report = self._read_json(path)
        except Exception as exc:
            return {
                "step": fallback_step["step"],
                "name": fallback_step["name"],
                "cycle": cycle,
                "decision": "changes_requested",
                "summary": f"Review report is not valid JSON: {exc}",
                "commands": [],
                "findings": [
                    {
                        "severity": "blocker",
                        "file": self._relative(path),
                        "line": None,
                        "message": "Review report could not be parsed.",
                    }
                ],
                "required_changes": ["Write a valid JSON review report."],
            }

        decision = report.get("decision")
        if decision not in self.REVIEW_DECISIONS:
            report["decision"] = "changes_requested"
            report.setdefault("findings", []).append(
                {
                    "severity": "blocker",
                    "file": self._relative(path),
                    "line": None,
                    "message": f"Invalid review decision: {decision!r}.",
                }
            )
            report.setdefault("required_changes", []).append("Use a valid decision: approved, changes_requested, or blocked.")
        return report

    def _run_implementation_until_ready(
        self,
        *,
        step: dict,
        guardrails: str,
        review_feedback: Optional[dict],
        cycle: int,
    ) -> None:
        step_num, step_name = step["step"], step["name"]
        prev_error = None

        for attempt in range(1, self.MAX_IMPLEMENTATION_ATTEMPTS + 1):
            index = self._read_json(self._index_file)
            current = self._step_record(index, step_num)
            if "started_at" not in current:
                current["started_at"] = self._stamp()
            current["status"] = "in_progress"
            current["implementation_attempt"] = attempt
            current["review_cycle"] = cycle
            self._write_json(self._index_file, index)

            preamble = self._build_implementation_preamble(
                guardrails=guardrails,
                step_context=self._build_step_context(index),
                prev_error=prev_error,
                review_feedback=review_feedback,
            )
            output_path = self._outputs_dir / f"step{step_num}-implementation-cycle{cycle}-attempt{attempt}.json"
            tag = f"Step {step_num}/{self._total - 1} implementation: {step_name}"
            if attempt > 1:
                tag += f" [attempt {attempt}/{self.MAX_IMPLEMENTATION_ATTEMPTS}]"

            with progress_indicator(tag) as pi:
                self._invoke_codex(step, preamble, output_path=output_path, label="implementation")
                elapsed = int(pi.elapsed)

            index = self._read_json(self._index_file)
            current = self._step_record(index, step_num)
            status = current.get("status", "pending")

            if status == "completed":
                current["status"] = "ready_for_review"
                current["completion_override"] = "Implementation agent attempted to mark completed; executor requires review approval."
                self._write_json(self._index_file, index)
                print(f"  ! Step {step_num}: implementation tried to complete; demoted to ready_for_review [{elapsed}s]")
                return

            if status == "ready_for_review":
                print(f"  > Step {step_num}: ready for review [{elapsed}s]")
                return

            if status == "blocked":
                current["blocked_at"] = self._stamp()
                self._write_json(self._index_file, index)
                print(f"  ! Step {step_num}: blocked [{elapsed}s]")
                print(f"    Reason: {current.get('blocked_reason', '')}")
                self._update_top_index("blocked")
                self._commit_housekeeping(f"chore({self._phase_name}): step {step_num} blocked")
                sys.exit(2)

            err_msg = current.get("error_message") or f"Step did not reach ready_for_review (status: {status})"
            if attempt < self.MAX_IMPLEMENTATION_ATTEMPTS:
                current["status"] = "pending"
                current.pop("error_message", None)
                self._write_json(self._index_file, index)
                prev_error = err_msg
                print(f"  retry Step {step_num}: implementation {attempt}/{self.MAX_IMPLEMENTATION_ATTEMPTS} - {err_msg}")
            else:
                current["status"] = "error"
                current["error_message"] = f"[{self.MAX_IMPLEMENTATION_ATTEMPTS} implementation attempts failed] {err_msg}"
                current["failed_at"] = self._stamp()
                self._write_json(self._index_file, index)
                self._update_top_index("error")
                self._commit_housekeeping(f"chore({self._phase_name}): step {step_num} implementation failed")
                print(f"  x Step {step_num}: implementation failed after {self.MAX_IMPLEMENTATION_ATTEMPTS} attempts [{elapsed}s]")
                print(f"    Error: {err_msg}")
                sys.exit(1)

    def _run_step_review(self, *, step: dict, guardrails: str, cycle: int) -> dict:
        step_num, step_name = step["step"], step["name"]
        report_path = self._reviews_dir / f"step{step_num}-review-cycle{cycle}.json"
        output_path = self._outputs_dir / f"step{step_num}-review-cycle{cycle}-output.json"
        index = self._read_json(self._index_file)
        prompt = self._build_review_prompt(
            guardrails=guardrails,
            step_context=self._build_step_context(index),
            step=step,
            cycle=cycle,
            report_path=report_path,
        )

        tag = f"Step {step_num}/{self._total - 1} review cycle {cycle}: {step_name}"
        with progress_indicator(tag) as pi:
            self._invoke_codex(step, "", output_path=output_path, prompt_body=prompt, label="review")
            elapsed = int(pi.elapsed)

        report = self._read_decision_report(report_path, fallback_step=step, cycle=cycle)
        print(f"  Review: Step {step_num} {report.get('decision')} [{elapsed}s]")
        return report

    def _execute_single_step(self, step: dict, guardrails: str) -> bool:
        step_num, step_name = step["step"], step["name"]
        review_feedback = None

        index = self._read_json(self._index_file)
        current = self._step_record(index, step_num)
        cycle = int(current.get("review_cycle", 0)) or 1

        while cycle <= self.MAX_REVIEW_CYCLES:
            index = self._read_json(self._index_file)
            current = self._step_record(index, step_num)

            if current.get("status") != "ready_for_review":
                self._run_implementation_until_ready(
                    step=step,
                    guardrails=guardrails,
                    review_feedback=review_feedback,
                    cycle=cycle,
                )

            report = self._run_step_review(step=step, guardrails=guardrails, cycle=cycle)
            decision = report.get("decision")

            if decision == "approved":
                index = self._read_json(self._index_file)
                current = self._step_record(index, step_num)
                current["status"] = "completed"
                current["completed_at"] = self._stamp()
                current["review_cycle"] = cycle
                current["review_summary"] = report.get("summary", "")
                current["review_report"] = self._relative(self._reviews_dir / f"step{step_num}-review-cycle{cycle}.json")
                current.setdefault("summary", f"{step_name} implemented and approved")
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                print(f"  OK Step {step_num}: {step_name} approved")
                return True

            if decision == "blocked":
                index = self._read_json(self._index_file)
                current = self._step_record(index, step_num)
                current["status"] = "blocked"
                current["blocked_at"] = self._stamp()
                current["blocked_reason"] = report.get("summary", "Review blocked")
                current["review_report"] = self._relative(self._reviews_dir / f"step{step_num}-review-cycle{cycle}.json")
                self._write_json(self._index_file, index)
                self._update_top_index("blocked")
                self._commit_housekeeping(f"chore({self._phase_name}): step {step_num} review blocked")
                print(f"  ! Step {step_num}: review blocked")
                sys.exit(2)

            if cycle >= self.MAX_REVIEW_CYCLES:
                index = self._read_json(self._index_file)
                current = self._step_record(index, step_num)
                current["status"] = "review_failed"
                current["review_failed_at"] = self._stamp()
                current["review_summary"] = report.get("summary", "Review cycles exhausted")
                current["review_report"] = self._relative(self._reviews_dir / f"step{step_num}-review-cycle{cycle}.json")
                self._write_json(self._index_file, index)
                self._update_top_index("review_failed")
                self._commit_housekeeping(f"chore({self._phase_name}): step {step_num} review failed")
                print(f"  x Step {step_num}: review failed after {self.MAX_REVIEW_CYCLES} cycles")
                sys.exit(1)

            index = self._read_json(self._index_file)
            current = self._step_record(index, step_num)
            current["status"] = "pending"
            current["review_cycle"] = cycle + 1
            current["last_review_decision"] = "changes_requested"
            current["last_review_report"] = self._relative(self._reviews_dir / f"step{step_num}-review-cycle{cycle}.json")
            current["review_summary"] = report.get("summary", "")
            self._write_json(self._index_file, index)
            review_feedback = report
            cycle += 1

        return False

    def _execute_all_steps(self, guardrails: str):
        while True:
            index = self._read_json(self._index_file)
            pending = next((s for s in index["steps"] if s.get("status", "pending") != "completed"), None)
            if pending is None:
                print("\n  All steps approved!")
                return

            if pending.get("status", "pending") in self.STEP_BLOCKING_STATUSES:
                self._check_blockers()
            self._execute_single_step(pending, guardrails)

    def _run_phase_eval(self, guardrails: str):
        report_path = self._eval_dir / "phase-eval.json"
        output_path = self._outputs_dir / "phase-eval-output.json"
        prompt = self._build_phase_eval_prompt(guardrails=guardrails, report_path=report_path)
        phase_step = {"step": "phase", "name": "phase-eval"}

        with progress_indicator("Phase evaluation") as pi:
            self._invoke_codex(phase_step, "", output_path=output_path, prompt_body=prompt, label="phase-eval")
            elapsed = int(pi.elapsed)

        report = self._read_decision_report(report_path, fallback_step=phase_step, cycle=1)
        decision = report.get("decision")
        index = self._read_json(self._index_file)
        index["phase_eval"] = {
            "decision": decision,
            "overallScore": report.get("overallScore"),
            "report": self._relative(report_path),
            "summary": report.get("summary", ""),
        }
        self._write_json(self._index_file, index)
        print(f"  Phase eval: {decision} [{elapsed}s]")

        if decision == "approved":
            return

        if decision == "blocked":
            index["blocked_at"] = self._stamp()
            index["blocked_reason"] = report.get("summary", "Phase evaluation blocked")
            self._write_json(self._index_file, index)
            self._update_top_index("blocked")
            self._commit_housekeeping(f"chore({self._phase_name}): phase evaluation blocked")
            sys.exit(2)

        index["review_failed_at"] = self._stamp()
        index["review_summary"] = report.get("summary", "Phase evaluation requested changes")
        self._write_json(self._index_file, index)
        self._update_top_index("review_failed")
        self._commit_housekeeping(f"chore({self._phase_name}): phase evaluation failed")
        sys.exit(1)

    def _finalize(self):
        index = self._read_json(self._index_file)
        index["completed_at"] = self._stamp()
        self._write_json(self._index_file, index)
        self._update_top_index("completed")

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = f"chore({self._phase_name}): mark phase completed"
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  OK {msg}")

        if self._auto_push:
            branch = f"feat-{self._phase_name}"
            r = self._run_git("push", "-u", "origin", branch)
            if r.returncode != 0:
                print(f"\n  ERROR: git push failed: {r.stderr.strip()}")
                sys.exit(1)
            print(f"  OK Pushed to origin/{branch}")

        print(f"\n{'=' * 60}")
        print(f"  Phase '{self._phase_name}' completed!")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Harness Step Executor")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 01-login)")
    parser.add_argument("--push", action="store_true", help="Push branch after completion")
    args = parser.parse_args()

    StepExecutor(args.phase_dir, auto_push=args.push).run()


if __name__ == "__main__":
    main()
