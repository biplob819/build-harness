#!/usr/bin/env python3
"""Install Build Harness into a project repository.

Writes the per-repo pieces a Claude Code plugin cannot ship: the harness scripts,
the constitution, standing principles, decision and lesson logs, the build graph,
the capability catalog, command gates, the first node's spec folder, and a git
pre-push hook. Never overwrites a file that already exists; it reports it instead.

Usage:
    python3 scripts/init.py /path/to/repo [--stack python|node|go|none] [--project NAME] [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TEMPLATES = HERE / "templates"
HARNESS = HERE / "harness"

GATES = {
    "python": [("lint", "both", "ruff check ."), ("tests", "both", "python3 -m pytest -q")],
    "node": [
        ("lint", "both", "npm run lint --if-present"),
        ("types", "converge", "npx tsc --noEmit"),
        ("tests", "both", "npm test --if-present"),
        ("build", "converge", "npm run build --if-present"),
    ],
    "go": [("vet", "both", "go vet ./..."), ("tests", "both", "go test ./...")],
    "none": [],
}

# template file -> destination in the target repo
PLACES = {
    "CLAUDE.md": "CLAUDE.md",
    "standing-principles.md": "docs/standing-principles.md",
    "decisions.md": "docs/decisions.md",
    "lessons.md": "docs/lessons.md",
    "changelog.md": "changelog.md",
    "graph.md": "docs/graph/graph.md",
    "catalog.tsv": "docs/graph/catalog.tsv",
    "harness.toml": "harness.toml",
    "spec/spec.md": "specs/W0.1-harness/spec.md",
    "spec/criteria.md": "specs/W0.1-harness/criteria.md",
    "spec/tasks.md": "specs/W0.1-harness/tasks.md",
    "spec/RUN-STATE.md": "specs/W0.1-harness/RUN-STATE.md",
}


def detect_stack(root: Path) -> str:
    if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        return "python"
    if (root / "package.json").is_file():
        return "node"
    if (root / "go.mod").is_file():
        return "go"
    return "none"


def fill(text: str, values: dict[str, str]) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def install(root: Path, stack: str, project: str, dry: bool) -> int:
    if not root.is_dir():
        print(f"init: {root} is not a directory")
        return 1
    values = {
        "project": project, "owner": "(your name)", "date": dt.date.today().isoformat(),
        "node": "W0.1", "title": "Repository and harness", "caps": "HAR-01",
    }
    wrote: list[str] = []
    kept: list[str] = []

    def put(dest_rel: str, content: str | None = None, src: Path | None = None, mode: int | None = None) -> None:
        dest = root / dest_rel
        if dest.exists():
            kept.append(dest_rel)
            return
        wrote.append(dest_rel)
        if dry:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src is not None:
            shutil.copyfile(src, dest)
        else:
            dest.write_text(content or "", encoding="utf-8")
        if mode:
            dest.chmod(dest.stat().st_mode | mode)

    for py in sorted(HARNESS.glob("*.py")):
        put(f"harness/{py.name}", src=py, mode=stat.S_IXUSR)
    rows = "\n".join("\t".join(r) for r in GATES[stack])
    put("harness/gates.tsv", "name\twhen\tcommand\n# when: converge | pre-push | both\n" + (rows + "\n" if rows else ""))
    for tpl, dest in PLACES.items():
        put(dest, fill((TEMPLATES / tpl).read_text(encoding="utf-8"), values))
    put(".harness/.gitignore", "*\n")

    git_dir = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=root, capture_output=True, text=True)
    if git_dir.returncode == 0:
        hooks = (root / git_dir.stdout.strip()) / "hooks"
        put(str((hooks / "pre-push").relative_to(root)), src=TEMPLATES / "git-hooks" / "pre-push", mode=stat.S_IXUSR)
    else:
        print("init: not a git repository; skipped the pre-push hook")

    print(f"Build Harness {'would install' if dry else 'installed'} into {root} (stack: {stack})")
    for w in wrote:
        print(f"  + {w}")
    for k in kept:
        print(f"  = {k} (exists, left as is)")
    if not dry:
        print("\nNext: edit docs/graph/graph.md and catalog.tsv for your product, then")
        print("  python3 harness/node_start.py W0.1 --mark-building")
        print("  python3 harness/node_converge.py W0.1")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--stack", choices=sorted(GATES), help="command gates preset (default: detect)")
    ap.add_argument("--project", help="project name for the constitution (default: folder name)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    root = args.repo.resolve()
    return install(root, args.stack or detect_stack(root), args.project or root.name, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
