import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".codex" / "hooks" / "deny-dangerous-command.sh"


def run_guard(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOK)],
        cwd=ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def command_payload(command: str) -> dict:
    return {
        "tool_name": "exec_command",
        "tool_input": {
            "cmd": command,
        },
    }


def test_blocks_rm_rf_command():
    result = run_guard(command_payload("rm -rf dist"))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    hook_output = output["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert "rm -rf" in hook_output["permissionDecisionReason"]


def test_blocks_force_push_command():
    result = run_guard(command_payload("git push --force origin main"))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_nested_command_field():
    result = run_guard(
        {
            "tool_name": "shell",
            "tool_input": {
                "arguments": {
                    "command": "git reset --hard HEAD~1",
                },
            },
        }
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_safe_command():
    result = run_guard(command_payload("npm run test"))

    assert result.returncode == 0
    assert result.stdout == ""
