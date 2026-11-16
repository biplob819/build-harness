#!/usr/bin/env python3
"""Measure what a harness actually did in one or more repositories, from git and the harness files.

Counts, per repo: commits and active days; nodes in the build graph and how many are green;
capability rows; command and structural gates; recorded decisions and lessons; and verifier
rounds, read from commit messages like "N1.2: ... (green after 3 verifier rounds)".
Prints a Markdown table, so the numbers in a README can be reproduced by anyone with the repos.

Usage:
    python3 scripts/evidence.py ~/code/repo-a ~/code/repo-b [--json]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROUNDS = re.compile(r"green after (\d+) verifier rounds?", re.I)
# Decisions and lessons as headings (## D-12), table rows (| D-12 |) or list items (- **L27**); unique ids.
DECISION = re.compile(r"^[#|*\-\s]{0,6}(D-\d+)\b", re.M)
LESSON = re.compile(r"^[#|*\-\s]{0,6}(L-?\d+)\b", re.M)
VERIFIER = re.compile(r"\bverifier\b", re.I)
NODE_ROW = re.compile(r"^\|\s*\**`?([A-Z]\d+\.\d+)`?\**\s*\|", re.M)


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ""


def first(repo: Path, patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for p in patterns:
        found += [f for f in repo.glob(p) if f.is_file() and "node_modules" not in f.parts and "archive" not in f.parts]
    return found


def count_rows(path: Path) -> int:
    rows = [r for r in csv.reader(path.read_text(encoding="utf-8", errors="replace").splitlines(), delimiter="\t")
            if r and not r[0].lstrip().startswith("#")]
    return max(0, len(rows) - 1)


def measure(repo: Path) -> dict[str, object]:
    log = git(repo, "log", "--format=%ad%x09%s", "--date=short")
    lines = [ln for ln in log.splitlines() if ln]
    days = {ln.split("\t", 1)[0] for ln in lines}
    rounds = [int(m) for ln in lines for m in ROUNDS.findall(ln)]
    graphs = first(repo, ["docs/graph/graph.md", "docs/**/graph.md"])
    nodes = sorted({n for g in graphs[:1] for n in NODE_ROW.findall(g.read_text(encoding="utf-8", errors="replace"))})
    catalogs = first(repo, ["docs/graph/catalog.tsv", "docs/**/catalog.tsv"])
    caps, green_caps, green_nodes = 0, 0, 0
    if catalogs:
        rows = list(csv.DictReader(catalogs[0].read_text(encoding="utf-8", errors="replace").splitlines(), delimiter="\t"))
        caps = len(rows)
        green_caps = sum(1 for r in rows if (r.get("status") or "").strip() == "green")
        by_node: dict[str, set[str]] = {}
        for r in rows:
            by_node.setdefault((r.get("node") or "").strip(), set()).add((r.get("status") or "").strip())
        green_nodes = sum(1 for s in by_node.values() if s == {"green"})
    gate_files = first(repo, ["harness/gates.tsv", "scripts/pre-push-gates.tsv"])
    gates = sum(count_rows(f) for f in gate_files)
    decisions = len({m for f in first(repo, ["docs/decisions.md", "docs/**/decisions.md", "decisions.md"])[:1]
                     for m in DECISION.findall(f.read_text(encoding="utf-8", errors="replace"))})
    lessons = len({m for f in first(repo, ["docs/lessons.md", "lessons*.md", "docs/**/lessons.md"])[:1]
                   for m in LESSON.findall(f.read_text(encoding="utf-8", errors="replace"))})
    verifier_commits = sum(1 for ln in lines if VERIFIER.search(ln))
    return {
        "repo": repo.name, "commits": len(lines), "active_days": len(days),
        "first": min(days) if days else "", "last": max(days) if days else "",
        "nodes": len(nodes), "green_nodes": green_nodes, "capabilities": caps, "green_capabilities": green_caps,
        "command_gates": gates, "decisions": decisions, "lessons": lessons,
        "verifier_rounds": sum(rounds), "verifier_commits": verifier_commits,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repos", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    results = [measure(r.expanduser().resolve()) for r in args.repos]
    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    cols = ["repo", "commits", "active_days", "nodes", "green_nodes", "capabilities", "green_capabilities",
            "command_gates", "decisions", "lessons", "verifier_commits"]
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in results:
        print("| " + " | ".join(str(r[c]) for c in cols) + " |")
    total = {c: sum(int(r[c]) for r in results) for c in cols[1:]}  # type: ignore[call-overload]
    print("| **total** | " + " | ".join(str(total[c]) for c in cols[1:]) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
