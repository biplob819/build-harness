"""Runs every self-test, the installer end to end, and the push guard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(*args: str, cwd: Path = ROOT, env: dict[str, str] | None = None, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, input=stdin, env={**os.environ, **(env or {})})


def test_node_start_self_test():
    assert run(PY, "harness/node_start.py", "--self-test").returncode == 0


def test_node_converge_self_test():
    assert run(PY, "harness/node_converge.py", "--self-test").returncode == 0


def test_secret_scan_self_test():
    assert run(PY, "harness/secret_scan.py", "--self-test").returncode == 0


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run("git", "init", "-q", "-b", "main", cwd=repo)
    run("git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "root", cwd=repo)
    out = run(PY, str(ROOT / "scripts" / "init.py"), str(repo), "--stack", "none")
    assert out.returncode == 0, out.stdout + out.stderr
    return repo


def test_init_installs_and_node_goes_green(tmp_path):
    repo = _init_repo(tmp_path)
    for f in ["CLAUDE.md", "harness/node_converge.py", "docs/graph/catalog.tsv", "specs/W0.1-harness/RUN-STATE.md"]:
        assert (repo / f).is_file(), f
    assert run(PY, "harness/node_start.py", "W0.1", "--mark-building", cwd=repo).returncode == 0
    (repo / "tests").mkdir()
    (repo / "tests" / "test_w01.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    cat = repo / "docs/graph/catalog.tsv"
    cat.write_text(
        cat.read_text(encoding="utf-8").replace(
            "HAR-01\tW0.1\tbuilding\t",
            'HAR-01\tW0.1\tgreen\tlogical=tests/test_w01.py›"test_a"; contract=tests/test_w01.py›"test_a"; safety=n/a:installer only writes local template files',
        ),
        encoding="utf-8",
    )
    out = run(PY, "harness/node_converge.py", "W0.1", "--no-log", cwd=repo)
    assert out.returncode == 0, out.stdout
    assert "RESULT: PASS" in out.stdout


def test_init_never_overwrites(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
    out = run(PY, str(ROOT / "scripts" / "init.py"), str(repo), "--stack", "none")
    assert "CLAUDE.md (exists, left as is)" in out.stdout
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == "mine\n"


def _guard(repo: Path, command: str) -> int:
    payload = json.dumps({"tool_input": {"command": command}})
    return run(PY, str(ROOT / "hooks" / "guard_bash.py"), env={"CLAUDE_PROJECT_DIR": str(repo)}, stdin=payload).returncode


def test_guard_blocks_bypass_and_force_and_bad_push(tmp_path):
    repo = _init_repo(tmp_path)
    assert _guard(repo, "git commit --no-verify -m x") == 2
    assert _guard(repo, "git push --force origin main") == 2
    assert _guard(repo, "git status") == 0
    assert _guard(repo, "git push origin main") == 0
    (repo / "leak.env").write_text("K=" + "sk-ant-" + "Qw7e" * 8 + "\n", encoding="utf-8")
    assert _guard(repo, "git push origin main") == 2


def test_guard_is_silent_outside_harnessed_repos(tmp_path):
    assert _guard(tmp_path, "git push --force") == 0
