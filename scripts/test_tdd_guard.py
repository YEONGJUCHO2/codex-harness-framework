import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".codex" / "hooks" / "tdd-guard.sh"


def run_guard(cwd: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOK)],
        cwd=cwd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def patch_payload(path: str) -> dict:
    return {
        "tool_name": "apply_patch",
        "tool_input": {
            "command": (
                "*** Begin Patch\n"
                f"*** Add File: {path}\n"
                "+export const value = 1;\n"
                "*** End Patch\n"
            )
        },
    }


def test_blocks_implementation_when_matching_test_is_missing(tmp_path):
    (tmp_path / "src" / "lib").mkdir(parents=True)

    result = run_guard(tmp_path, patch_payload("src/lib/channel-url.ts"))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    hook_output = output["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert "TDD GUARD" in hook_output["permissionDecisionReason"]


def test_allows_implementation_when_matching_test_exists(tmp_path):
    target_dir = tmp_path / "src" / "lib"
    target_dir.mkdir(parents=True)
    (target_dir / "channel-url.test.ts").write_text("test('exists', () => {})")

    result = run_guard(tmp_path, patch_payload("src/lib/channel-url.ts"))

    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_docs_and_test_files(tmp_path):
    result = run_guard(tmp_path, patch_payload("docs/ARCHITECTURE.md"))
    assert result.returncode == 0
    assert result.stdout == ""

    result = run_guard(tmp_path, patch_payload("src/lib/channel-url.test.ts"))
    assert result.returncode == 0
    assert result.stdout == ""
