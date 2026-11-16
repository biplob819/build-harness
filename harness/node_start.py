#!/usr/bin/env python3
"""Decide whether a build node may start.

A node may start when:
  1. it exists in the graph and has capability rows in the catalog,
  2. the graph stays eligible with this node starting (every dependency green, no cycles),
  3. specs/<node>-<slug>/ holds spec.md, criteria.md and tasks.md,
  4. criteria.md names every capability of the node.

Usage:
    python3 harness/node_start.py N1.1                   # check only, writes nothing
    python3 harness/node_start.py N1.1 --mark-building   # check, record baseline, flip rows
    python3 harness/node_start.py --self-test

Exit 0 means go, 1 means do not start.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from harness_lib import (
    ROOT,
    Cap,
    HarnessError,
    Node,
    eligibility_problems,
    load_catalog,
    load_config,
    load_graph,
    node_status,
    parse_catalog,
    parse_graph,
    spec_dir,
    write_catalog,
)

SPEC_FILES = ("spec.md", "criteria.md", "tasks.md")


def check_start(node_id: str, nodes: dict[str, Node], caps: list[Cap], specs: Path) -> list[str]:
    if node_id not in nodes:
        return [f"unknown node {node_id}"]
    problems: list[str] = []
    rows = [c for c in caps if c.node == node_id]
    if not rows:
        problems.append(f"{node_id} has no capability rows in the catalog")
    problems += eligibility_problems(nodes, caps, simulate_start=node_id)
    d = spec_dir(node_id, specs)
    if d is None:
        problems.append(f"no spec folder {specs.name}/{node_id}-<slug>/")
        return problems
    for f in SPEC_FILES:
        if not (d / f).is_file():
            problems.append(f"missing {d.name}/{f}")
    criteria = d / "criteria.md"
    if criteria.is_file():
        text = criteria.read_text(encoding="utf-8")
        missing = [c.cap_id for c in rows if c.cap_id not in text]
        if missing:
            problems.append(f"criteria.md does not cover: {', '.join(missing)}")
    return problems


def _git_head(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
        )
    except OSError:
        return "none"
    return out.stdout.strip() if out.returncode == 0 else "none"


def self_test() -> int:
    graph = parse_graph("| **W0.1** | Harness | — |\n| **N1.1** | Schemas | W0.1 |\n")
    hdr = "cap_id\tnode\tstatus\tproof\tnote\n"
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        specs = Path(tmp) / "specs"
        good = specs / "N1.1-schemas"
        good.mkdir(parents=True)
        for f in SPEC_FILES:
            (good / f).write_text("SCH-01 SCH-02\n", encoding="utf-8")
        ok_catalog = hdr + "H-1\tW0.1\tgreen\t\t\nSCH-01\tN1.1\tspec\t\t\nSCH-02\tN1.1\tspec\t\t\n"
        cases = [
            ("all good", "N1.1", ok_catalog, True),
            ("dependency not green", "N1.1", hdr + "H-1\tW0.1\tbuilding\t\t\nSCH-01\tN1.1\tspec\t\t\n", False),
            ("cap missing from criteria", "N1.1", hdr + "H-1\tW0.1\tgreen\t\t\nSCH-03\tN1.1\tspec\t\t\n", False),
            ("no catalog rows", "N1.1", hdr + "H-1\tW0.1\tgreen\t\t\n", False),
            ("no spec folder", "W0.1", hdr + "H-1\tW0.1\tspec\t\t\n", False),
            ("unknown node", "Z1.1", hdr, False),
        ]
        for name, node, cat, expect_ok in cases:
            problems = check_start(node, graph, parse_catalog(cat), specs)
            ok = not problems
            failures += ok != expect_ok
            print(f"  [{'ok' if ok == expect_ok else 'WRONG'}] {name}: {'go' if ok else problems[0]}")
        (good / "tasks.md").unlink()
        problems = check_start("N1.1", graph, parse_catalog(ok_catalog), specs)
        ok = any("tasks.md" in p for p in problems)
        failures += not ok
        print(f"  [{'ok' if ok else 'WRONG'}] missing tasks.md detected")
    print("self-test", "PASSED" if failures == 0 else f"FAILED ({failures})")
    return 0 if failures == 0 else 1


def start(node_id: str, root: Path = ROOT, *, mark_building: bool = False, reset_base: bool = False) -> int:
    """Check a node; with mark_building, record the changed-tests baseline and flip rows.

    A check-only run writes nothing. An existing .base is kept unless reset_base, so
    re-running node-start mid-build cannot move the changed-tests baseline.
    """
    try:
        cfg = load_config(root)
        nodes = load_graph(cfg)
        caps = load_catalog(cfg)
    except (HarnessError, OSError) as exc:
        print(f"node-start: cannot read inputs: {exc}")
        return 1
    problems = check_start(node_id, nodes, caps, cfg.specs)
    node = nodes.get(node_id)
    if node:
        print(f"node-start {node.id} — {node.title}")
        for d in node.depends_on:
            print(f"  depends on {d}: {node_status(d, caps)}")
        rows = [c for c in caps if c.node == node.id]
        print(f"  capabilities: {len(rows)} ({', '.join(c.cap_id for c in rows)})")
    if problems:
        print("DO NOT START:")
        for p in problems:
            print(f"  - {p}")
        return 1
    if mark_building:
        d = spec_dir(node_id, cfg.specs)
        assert d is not None
        base = d / ".base"
        if reset_base or not base.is_file():
            base.write_text(_git_head(root) + "\n", encoding="utf-8")
            print(f"  changed-tests baseline: {base.read_text(encoding='utf-8').strip()[:12]}")
        else:
            print(f"  keeping existing baseline {base.read_text(encoding='utf-8').strip()[:12]}")
        for c in caps:
            if c.node == node_id and c.status in ("not-started", "spec"):
                c.status = "building"
        write_catalog(caps, cfg.catalog)
        print("  rows flipped to building")
    print("GO")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("node", nargs="?")
    ap.add_argument("--mark-building", action="store_true", help="record the baseline and flip this node's rows to building")
    ap.add_argument("--reset-base", action="store_true", help="overwrite an existing baseline")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.node:
        ap.error("node is required")
    return start(args.node, mark_building=args.mark_building, reset_base=args.reset_base)


if __name__ == "__main__":
    sys.exit(main())
