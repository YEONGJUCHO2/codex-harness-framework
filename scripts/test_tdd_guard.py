import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".codex" / "hooks" / "tdd-guard.sh"


def run_guard(cwd: Path, payload: dict, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOK)],
        cwd=cwd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
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


def patch_field_payload(path: str) -> dict:
    return {
        "tool_name": "apply_patch",
        "tool_input": {
            "patch": (
                "*** Begin Patch\n"
                f"*** Add File: {path}\n"
                "+export const value = 1;\n"
                "*** End Patch\n"
            )
        },
    }


def raw_patch_payload(path: str) -> dict:
    return {
        "tool_name": "apply_patch",
        "tool_input": (
            "*** Begin Patch\n"
            f"*** Add File: {path}\n"
            "+export const value = 1;\n"
            "*** End Patch\n"
        ),
    }


def test_blocks_implementation_when_matching_test_is_missing(tmp_path):
    (tmp_path / "src" / "lib").mkdir(parents=True)

    result = run_guard(tmp_path, patch_payload("src/lib/channel-url.ts"))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    hook_output = output["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert "TDD GUARD" in hook_output["permissionDecisionReason"]


def test_blocks_patch_field_payload_when_matching_test_is_missing(tmp_path):
    (tmp_path / "src" / "lib").mkdir(parents=True)

    result = run_guard(tmp_path, patch_field_payload("src/lib/channel-url.ts"))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_raw_patch_payload_when_matching_test_is_missing(tmp_path):
    (tmp_path / "src" / "lib").mkdir(parents=True)

    result = run_guard(tmp_path, raw_patch_payload("src/lib/channel-url.ts"))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_implementation_when_matching_test_exists(tmp_path):
    target_dir = tmp_path / "src" / "lib"
    target_dir.mkdir(parents=True)
    (target_dir / "channel-url.test.ts").write_text("test('exists', () => {})")

    result = run_guard(tmp_path, patch_payload("src/lib/channel-url.ts"))

    assert result.returncode == 0
    assert result.stdout == ""


def test_uses_codex_project_dir_when_current_directory_is_not_project_root(tmp_path):
    project = tmp_path / "project"
    target_dir = project / "src" / "lib"
    target_dir.mkdir(parents=True)
    tests_dir = project / "src" / "__tests__"
    tests_dir.mkdir(parents=True)
    (tests_dir / "channel-url.test.ts").write_text("test('exists', () => {})")

    result = run_guard(
        tmp_path,
        patch_payload("src/lib/channel-url.ts"),
        env={**os.environ, "CODEX_PROJECT_DIR": str(project)},
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_docs_and_test_files(tmp_path):
    result = run_guard(tmp_path, patch_payload("docs/ARCHITECTURE.md"))
    assert result.returncode == 0
    assert result.stdout == ""

    result = run_guard(tmp_path, patch_payload("src/lib/channel-url.test.ts"))
    assert result.returncode == 0
    assert result.stdout == ""
