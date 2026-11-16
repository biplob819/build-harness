#!/usr/bin/env python3
"""Run every gate for a build node and report all of them, even after a failure.

Usage:
    python3 harness/node_converge.py N1.1             # run every gate for node N1.1
    python3 harness/node_converge.py --pre-push       # only the command gates marked pre-push, plus secrets
    python3 harness/node_converge.py --self-test      # prove every structural gate can fail

Exit 0 only when no gate FAILs. SKIP means the gate had nothing to check yet; SKIP never hides a failure.

Structural gates (built in):
  claims-work     at least one capability row of the node is building or green
  eligibility     no cycles, and nothing builds ahead of its dependencies
  proofs          every row cites a real, unskipped test for each proof dimension, or n/a:<reason>
  secrets         nothing that looks like a credential is in the tree
  changed-tests   if source changed since the node started, tests changed too
  records         changelog entry, criteria cover every row, RUN-STATE.md exists

Command gates come from harness/gates.tsv (lint, type-check, tests, build: whatever your stack uses).
Each row: name, when (converge | pre-push | both), command. A non-zero exit is a FAIL.
"""

from __future__ import annotations

import argparse
import ast
import csv
import datetime as dt
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import secret_scan
from harness_lib import (
    ROOT,
    Cap,
    Config,
    HarnessError,
    Node,
    eligibility_problems,
    load_catalog,
    load_config,
    load_graph,
    matches_any,
    parse_catalog,
    parse_graph,
    spec_dir,
)

NA_MIN_REASON = 10
GATE_FIELDS = ("name", "when", "command")
PROOF_RE = re.compile(r'^(?P<path>[^›"]+)›"(?P<test>[^"]+)"$')


@dataclass
class Result:
    status: str  # PASS | FAIL | SKIP
    detail: str


@dataclass
class Ctx:
    node: str
    cfg: Config
    nodes: dict[str, Node]
    caps: list[Cap]


def _run(cmd: list[str] | str, cwd: Path, timeout: int = 1800) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    return p.returncode, (p.stdout + p.stderr).strip()


def _tail(text: str, n: int = 12) -> str:
    return "\n".join(text.splitlines()[-n:])


# ---------- structural gates ----------


def gate_claims_work(ctx: Ctx) -> Result:
    rows = [c for c in ctx.caps if c.node == ctx.node]
    active = [c for c in rows if c.status in ("building", "green")]
    if not rows:
        return Result("FAIL", f"{ctx.node} has no catalog rows")
    if not active:
        return Result("FAIL", f"no row of {ctx.node} is building or green (run node_start.py --mark-building)")
    return Result("PASS", f"{len(active)}/{len(rows)} rows active")


def gate_eligibility(ctx: Ctx) -> Result:
    problems = eligibility_problems(ctx.nodes, ctx.caps)
    return Result("FAIL", "; ".join(problems)) if problems else Result("PASS", "eligible")


def _python_tests(path: Path) -> dict[str, bool]:
    """Map each real test function to whether it is skipped (module level or inside a Test* class)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, bool] = {}

    def record(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if fn.name.startswith("test"):
            found[fn.name] = any("skip" in ast.unparse(d) for d in fn.decorator_list)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            record(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    record(item)
    return found


def _named_test(path: Path, test: str) -> tuple[bool, bool]:
    """(found, skipped). Python files are parsed; other files must contain the quoted test title."""
    if path.suffix == ".py":
        tests = _python_tests(path)
        return (test in tests, tests.get(test, False))
    text = path.read_text(encoding="utf-8", errors="replace")
    for q in ('"', "'", "`"):
        i = text.find(f"{q}{test}{q}")
        if i >= 0:
            line = text[text.rfind("\n", 0, i) + 1 : i]
            return True, bool(re.search(r"\b(?:it|test|describe)\.(?:skip|todo)\b|\bx(?:it|test)\b", line))
    return False, False


def proof_problems(cap: Cap, cfg: Config) -> list[str]:
    if not cap.proof:
        return [f"{cap.cap_id}: no proof"]
    entries: dict[str, str] = {}
    for part in (p.strip() for p in cap.proof.split(";")):
        if not part:
            continue
        if "=" not in part:
            return [f"{cap.cap_id}: malformed proof entry {part!r}"]
        key, value = (s.strip() for s in part.split("=", 1))
        if key in entries:
            return [f"{cap.cap_id}: duplicate proof key {key!r}"]
        entries[key] = value
    problems: list[str] = []
    tests_root = cfg.tests_dir.resolve()
    for dim in cfg.proof_dimensions:
        value = entries.get(dim)
        if value is None:
            problems.append(f"{cap.cap_id}: missing {dim} proof")
            continue
        if value.startswith("n/a:"):
            if dim in cfg.proof_required:
                problems.append(f"{cap.cap_id}: {dim} proof cannot be n/a")
            elif len(value[4:].strip()) < NA_MIN_REASON:
                problems.append(f"{cap.cap_id}: {dim} n/a needs a reason of {NA_MIN_REASON}+ characters")
            continue
        m = PROOF_RE.match(value)
        if not m:
            problems.append(f'{cap.cap_id}: {dim} proof must be path›"test name" or n/a:<reason>')
            continue
        rel, test = m["path"].strip(), m["test"].strip()
        path = (cfg.root / rel).resolve()
        if not path.is_relative_to(tests_root):
            problems.append(f"{cap.cap_id}: {dim} proof file {rel} must be under {cfg.tests_dir.name}/")
            continue
        if not path.is_file():
            problems.append(f"{cap.cap_id}: {dim} proof file {rel} not found")
            continue
        try:
            found, skipped = _named_test(path, test)
        except SyntaxError as exc:
            problems.append(f"{cap.cap_id}: {dim} proof file {rel} does not parse: {exc.msg}")
            continue
        if not found:
            problems.append(f"{cap.cap_id}: {dim} test {test!r} not found in {rel}")
        elif skipped:
            problems.append(f"{cap.cap_id}: {dim} test {test!r} is skipped")
    extra = set(entries) - set(cfg.proof_dimensions)
    if extra:
        problems.append(f"{cap.cap_id}: unknown proof keys {sorted(extra)}")
    return problems


def gate_proofs(ctx: Ctx) -> Result:
    rows = [c for c in ctx.caps if c.node == ctx.node and c.status == "green"]
    if not rows:
        return Result("SKIP", "no green rows yet; proofs are checked when a row flips green")
    problems = [p for c in rows for p in proof_problems(c, ctx.cfg)]
    if problems:
        more = f"; … {len(problems) - 6} more" if len(problems) > 6 else ""
        return Result("FAIL", "; ".join(problems[:6]) + more)
    return Result("PASS", f"{len(rows)} green rows, every dimension proven")


def gate_secrets(ctx: Ctx) -> Result:
    hits = secret_scan.scan(secret_scan.candidate_files(ctx.cfg.root))
    return Result("FAIL", "\n".join(hits[:8])) if hits else Result("PASS", "no credentials found")


def changed_files(root: Path, base: str) -> list[str] | None:
    """Files changed since base: committed, staged, unstaged and untracked. None when git is unusable."""
    code, _ = _run(["git", "rev-parse", "--git-dir"], root)
    if code != 0:
        return None
    files: set[str] = set()
    code, _ = _run(["git", "rev-parse", "HEAD"], root)
    if code == 0 and base not in ("", "none"):
        code, out = _run(["git", "diff", "--name-only", base], root)
        if code != 0:
            raise HarnessError(f"git diff against base {base!r} failed: {_tail(out, 2)}")
        files.update(out.splitlines())
    else:
        files.update(_run(["git", "ls-files"], root)[1].splitlines())
    files.update(_run(["git", "ls-files", "--others", "--exclude-standard"], root)[1].splitlines())
    return sorted(f for f in files if f)


def changed_tests_problem(files: list[str], cfg: Config) -> str | None:
    tests = [f for f in files if matches_any(f, cfg.test_globs)]
    src = [f for f in files if matches_any(f, cfg.source_globs) and f not in tests]
    if src and not tests:
        return f"{len(src)} source files changed but no tests changed (e.g. {src[0]})"
    return None


def gate_changed_tests(ctx: Ctx) -> Result:
    d = spec_dir(ctx.node, ctx.cfg.specs)
    base_file = d / ".base" if d else None
    base = base_file.read_text(encoding="utf-8").strip() if base_file and base_file.is_file() else "none"
    try:
        files = changed_files(ctx.cfg.root, base)
    except HarnessError as exc:
        return Result("FAIL", str(exc))
    if files is None:
        return Result("SKIP", "not a git repository")
    problem = changed_tests_problem(files, ctx.cfg)
    if problem:
        return Result("FAIL", problem)
    return Result("PASS", f"{len(files)} files changed since {base[:10]}; tests changed with source")


def records_problems(node: str, caps: list[Cap], cfg: Config) -> list[str]:
    problems: list[str] = []
    if not cfg.changelog.is_file() or f"[{node}]" not in cfg.changelog.read_text(encoding="utf-8"):
        problems.append(f"{cfg.changelog.name} has no [{node}] entry")
    d = spec_dir(node, cfg.specs)
    if d is None:
        return [*problems, f"no spec folder for {node}"]
    criteria = d / "criteria.md"
    text = criteria.read_text(encoding="utf-8") if criteria.is_file() else ""
    missing = [c.cap_id for c in caps if c.node == node and c.cap_id not in text]
    if missing:
        problems.append(f"criteria.md misses {', '.join(missing)}")
    if not (d / "RUN-STATE.md").is_file():
        problems.append("RUN-STATE.md missing")
    return problems


def gate_records(ctx: Ctx) -> Result:
    problems = records_problems(ctx.node, ctx.caps, ctx.cfg)
    return Result("FAIL", "; ".join(problems)) if problems else Result("PASS", "records complete")


STRUCTURAL: list[tuple[str, Callable[[Ctx], Result]]] = [
    ("claims-work", gate_claims_work),
    ("eligibility", gate_eligibility),
    ("proofs", gate_proofs),
    ("secrets", gate_secrets),
]
CLOSING: list[tuple[str, Callable[[Ctx], Result]]] = [
    ("changed-tests", gate_changed_tests),
    ("records", gate_records),
]


# ---------- command gates ----------


def load_command_gates(path: Path) -> list[tuple[str, str, str]]:
    if not path.is_file():
        return []
    rows = [r for r in csv.reader(path.read_text(encoding="utf-8").splitlines(), delimiter="\t")
            if r and not r[0].lstrip().startswith("#")]
    if not rows or tuple(c.strip() for c in rows[0]) != GATE_FIELDS:
        raise HarnessError(f"{path.name} header must be exactly: " + " | ".join(GATE_FIELDS))
    gates: list[tuple[str, str, str]] = []
    for i, r in enumerate(rows[1:], start=2):
        if len(r) != 3:
            raise HarnessError(f"{path.name} row {i}: expected 3 tab-separated columns")
        name, when, command = (c.strip() for c in r)
        if when not in ("converge", "pre-push", "both"):
            raise HarnessError(f"{path.name} row {i}: when must be converge, pre-push or both")
        gates.append((name, when, command))
    return gates


def command_gate(command: str, root: Path) -> Result:
    code, out = _run(command, root)
    if code == 0:
        return Result("PASS", command)
    return Result("FAIL", f"`{command}` exited {code}\n{_tail(out)}")


# ---------- runner ----------


def run(gates: list[tuple[str, Callable[[], Result]]], title: str) -> tuple[str, int]:
    lines = [f"{title} — {dt.datetime.now().isoformat(timespec='seconds')}"]
    failed = 0
    for i, (name, fn) in enumerate(gates, start=1):
        try:
            r = fn()
        except Exception as exc:  # a crashing gate is a failing gate
            r = Result("FAIL", f"gate crashed: {exc!r}")
        failed += r.status == "FAIL"
        first, *rest = r.detail.splitlines() or [""]
        lines.append(f"{i:>2} {name:<14} {r.status:<4}  {first}")
        lines.extend(f"{'':>22}{ln}" for ln in rest)
    lines.append(f"RESULT: {'FAIL' if failed else 'PASS'} ({failed} failing gate{'s' if failed != 1 else ''})")
    return "\n".join(lines), failed


def converge(node: str, root: Path = ROOT, log: bool = True) -> int:
    try:
        cfg = load_config(root)
        ctx = Ctx(node, cfg, load_graph(cfg), load_catalog(cfg))
        commands = load_command_gates(cfg.gates)
    except (HarnessError, OSError) as exc:
        print(f"node-converge: cannot read inputs: {exc}")
        return 1
    if node not in ctx.nodes:
        print(f"node-converge: unknown node {node}")
        return 1
    gates: list[tuple[str, Callable[[], Result]]] = [(n, (lambda f=f: f(ctx))) for n, f in STRUCTURAL]
    gates += [(n, (lambda c=c: command_gate(c, root))) for n, w, c in commands if w in ("converge", "both")]
    gates += [(n, (lambda f=f: f(ctx))) for n, f in CLOSING]
    report, failed = run(gates, f"node-converge {node}")
    print(report)
    if log:
        log_dir = root / ".harness" / node
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"converge-{dt.datetime.now():%Y%m%dT%H%M%S}.txt").write_text(report + "\n", encoding="utf-8")
    return 1 if failed else 0


def pre_push(root: Path = ROOT) -> int:
    try:
        cfg = load_config(root)
        commands = load_command_gates(cfg.gates)
    except (HarnessError, OSError) as exc:
        print(f"pre-push: cannot read inputs: {exc}")
        return 1
    hits = lambda: Result("FAIL", "\n".join(h[:8])) if (h := secret_scan.scan(secret_scan.candidate_files(root))) else Result("PASS", "no credentials found")  # noqa: E731
    gates: list[tuple[str, Callable[[], Result]]] = [("secrets", hits)]
    gates += [(n, (lambda c=c: command_gate(c, root))) for n, w, c in commands if w in ("pre-push", "both")]
    report, failed = run(gates, "pre-push gates")
    print(report)
    return 1 if failed else 0


# ---------- self-test ----------


def self_test() -> int:
    failures = 0

    def check(name: str, ok: bool) -> None:
        nonlocal failures
        failures += not ok
        print(f"  [{'ok' if ok else 'WRONG'}] {name}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "tests").mkdir()
        (root / "tests" / "test_x.py").write_text(
            "import pytest\n\ndef test_real():\n    assert True\n\n@pytest.mark.skip\ndef test_skipped():\n    pass\n",
            encoding="utf-8",
        )
        (root / "tests" / "x.test.ts").write_text("it('adds numbers', () => {});\nit.skip('later', () => {});\n", encoding="utf-8")
        cfg = load_config(root)
        good = 'logical=tests/test_x.py›"test_real"; contract=tests/x.test.ts›"adds numbers"; safety=n/a:pure function, no input crosses a trust boundary'
        mk = lambda proof: Cap("C-1", "N1.1", "green", proof, "")  # noqa: E731
        check("proofs: valid python + ts + n/a pass", proof_problems(mk(good), cfg) == [])
        check("proofs: missing dimension fails", bool(proof_problems(mk('logical=tests/test_x.py›"test_real"'), cfg)))
        check("proofs: skipped python test fails", bool(proof_problems(mk(good.replace("test_real", "test_skipped")), cfg)))
        check("proofs: skipped ts test fails", bool(proof_problems(mk(good.replace("adds numbers", "later")), cfg)))
        check("proofs: unknown test name fails", bool(proof_problems(mk(good.replace("test_real", "test_nope")), cfg)))
        check("proofs: logical n/a refused", bool(proof_problems(mk(good.replace('tests/test_x.py›"test_real"', "n/a:no logic to test here at all")), cfg)))
        check("proofs: short n/a reason refused", bool(proof_problems(mk(good.replace("pure function, no input crosses a trust boundary", "none")), cfg)))
        check("proofs: file outside tests/ refused", bool(proof_problems(mk(good.replace("tests/test_x.py", "src/x.py")), cfg)))

        graph = parse_graph("| **W0.1** | Harness | — |\n| **N1.1** | Core | W0.1 |\n")
        hdr = "cap_id\tnode\tstatus\tproof\tnote\n"
        ahead = Ctx("N1.1", cfg, graph, parse_catalog(hdr + "H-1\tW0.1\tbuilding\t\t\nC-1\tN1.1\tbuilding\t\t\n"))
        check("eligibility: building ahead of dependency fails", gate_eligibility(ahead).status == "FAIL")
        idle = Ctx("N1.1", cfg, graph, parse_catalog(hdr + "H-1\tW0.1\tgreen\t\t\nC-1\tN1.1\tspec\t\t\n"))
        check("claims-work: no active row fails", gate_claims_work(idle).status == "FAIL")

        check("changed-tests: source without tests fails", changed_tests_problem(["src/app.py"], cfg) is not None)
        check("changed-tests: source with tests passes", changed_tests_problem(["src/app.py", "tests/test_app.py"], cfg) is None)
        check("changed-tests: docs only passes", changed_tests_problem(["README.md"], cfg) is None)

        check("records: missing changelog, spec and run-state fail", len(records_problems("N1.1", idle.caps, cfg)) >= 2)
        leak = root / "leak.env"
        leak.write_text("OPENAI=" + "sk-proj-" + "Q7w8" * 10 + "\n", encoding="utf-8")
        check("secrets: planted key is caught", bool(secret_scan.scan([leak])))
        (root / "harness").mkdir()
        (root / "harness" / "gates.tsv").write_text("name\twhen\tcommand\nfalse\tboth\tfalse\n", encoding="utf-8")
        gates = load_command_gates(root / "harness" / "gates.tsv")
        check("command gates: a failing command fails", command_gate(gates[0][2], root).status == "FAIL")
        (root / "harness" / "gates.tsv").write_text("name\twhen\tcommand\nx\tsometimes\ttrue\n", encoding="utf-8")
        try:
            load_command_gates(root / "harness" / "gates.tsv")
            check("command gates: bad 'when' rejected", False)
        except HarnessError:
            check("command gates: bad 'when' rejected", True)
    print("self-test", "PASSED" if failures == 0 else f"FAILED ({failures})")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("node", nargs="?")
    ap.add_argument("--pre-push", action="store_true", help="run the secret scan and the pre-push command gates only")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-log", action="store_true", help="do not write a log under .harness/")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.pre_push:
        return pre_push()
    if not args.node:
        ap.error("node is required (or --pre-push)")
    return converge(args.node, log=not args.no_log)


if __name__ == "__main__":
    sys.exit(main())
