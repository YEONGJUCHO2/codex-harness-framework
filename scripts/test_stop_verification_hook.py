import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".codex" / "hooks" / "stop-verification.sh"


def run_guard(cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOK)],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_runs_lint_build_test_in_original_claude_order(tmp_path):
    package_json = tmp_path / "package.json"
    package_json.write_text('{"scripts":{"lint":"x","build":"x","test":"x"}}')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "npm.log"
    fake_npm = bin_dir / "npm"
    fake_npm.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$NPM_LOG\"\n"
    )
    fake_npm.chmod(0o755)

    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "NPM_LOG": str(log_path)}
    result = run_guard(tmp_path, env=env)

    assert result.returncode == 0
    assert log_path.read_text().splitlines() == ["run lint", "run build", "run test"]


def test_skips_when_package_json_is_absent(tmp_path):
    result = run_guard(tmp_path)

    assert result.returncode == 0
    assert result.stdout == ""


def test_propagates_failed_verification_command(tmp_path):
    package_json = tmp_path / "package.json"
    package_json.write_text('{"scripts":{"lint":"x","build":"x","test":"x"}}')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_npm = bin_dir / "npm"
    fake_npm.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$2\" = \"build\" ]; then exit 42; fi\n"
    )
    fake_npm.chmod(0o755)

    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    result = run_guard(tmp_path, env=env)

    assert result.returncode == 42
