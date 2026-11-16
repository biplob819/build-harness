#!/usr/bin/env python3
"""Build Harness PreToolUse guard for Bash.

- Blocks commands that bypass git hooks (--no-verify) or force-push.
- Before any `git push`, runs the project's pre-push gates (secret scan plus the command
  gates marked pre-push or both in harness/gates.tsv) and blocks the push if one fails.
Does nothing in a repository without Build Harness installed. Exit 2 blocks the call and
shows stderr to Claude; exit 0 lets it run.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

BYPASS = re.compile(r"--no-verify\b|\bgit\b[^;&|\n]*\bcommit\b[^;&|\n]*\s-n\b")
PUSH = re.compile(r"\bgit\b[^;&|\n]*\bpush\b")
FORCE = re.compile(r"\bgit\b[^;&|\n]*\bpush\b[^;&|\n]*(?:\s--force\b|\s-f\b|\s--force-with-lease\b|\s\+\S)")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
    if not (project / "harness" / "node_converge.py").is_file():
        return 0
    if BYPASS.search(command):
        print("Build Harness: bypassing git hooks (--no-verify) is not allowed. Fix the failing gate instead.", file=sys.stderr)
        return 2
    if FORCE.search(command):
        print("Build Harness: force-pushing needs the owner. Ask them; do not work around this guard.", file=sys.stderr)
        return 2
    if PUSH.search(command):
        out = subprocess.run(
            [sys.executable, str(project / "harness" / "node_converge.py"), "--pre-push"],
            cwd=project, capture_output=True, text=True,
        )
        if out.returncode != 0:
            print("Build Harness: pre-push gates failed, push blocked.\n" + (out.stdout + out.stderr)[-3000:], file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
