"""Shared helpers for Build Harness: config, the build graph, the capability catalog.

The build graph lives in a markdown table (default docs/graph/graph.md). The capability
ledger lives in a TSV file (default docs/graph/catalog.tsv). Settings come from
harness.toml at the repo root; every key is optional. Nothing here touches the network.
"""

from __future__ import annotations

import csv
import fnmatch
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATUSES = ("not-started", "spec", "building", "green")
NODE_RE = re.compile(r"^[A-Z]\d+\.\d+$")
NODE_LIKE_RE = re.compile(r"^[A-Za-z]+\d+\.\d+$")  # looks like a node id but may be malformed
CATALOG_FIELDS = ("cap_id", "node", "status", "proof", "note")

DEFAULTS: dict[str, object] = {
    "graph": "docs/graph/graph.md",
    "catalog": "docs/graph/catalog.tsv",
    "specs": "specs",
    "gates": "harness/gates.tsv",
    "changelog": "changelog.md",
    # Every capability row must prove itself on each dimension, or say why not (n/a:<reason>).
    "proof_dimensions": ["logical", "contract", "safety"],
    # Dimensions that may never be n/a.
    "proof_required": ["logical"],
    "tests_dir": "tests",
    # If any file matching source_globs changed since a node started, a test file must change too.
    "source_globs": ["src/**", "lib/**", "app/**"],
    "test_globs": ["tests/**", "test/**", "**/*.test.*", "**/*_test.*", "**/test_*.py"],
}


@dataclass
class Config:
    root: Path
    graph: Path
    catalog: Path
    specs: Path
    gates: Path
    changelog: Path
    proof_dimensions: list[str]
    proof_required: list[str]
    tests_dir: Path
    source_globs: list[str]
    test_globs: list[str]


def load_config(root: Path = ROOT) -> Config:
    raw: dict[str, object] = dict(DEFAULTS)
    path = root / "harness.toml"
    if path.is_file():
        data = tomllib.loads(path.read_text(encoding="utf-8")).get("harness", {})
        unknown = set(data) - set(DEFAULTS)
        if unknown:
            raise HarnessError(f"harness.toml: unknown keys {sorted(unknown)}")
        raw.update(data)
    return Config(
        root=root,
        graph=root / str(raw["graph"]),
        catalog=root / str(raw["catalog"]),
        specs=root / str(raw["specs"]),
        gates=root / str(raw["gates"]),
        changelog=root / str(raw["changelog"]),
        proof_dimensions=list(raw["proof_dimensions"]),  # type: ignore[arg-type]
        proof_required=list(raw["proof_required"]),  # type: ignore[arg-type]
        tests_dir=root / str(raw["tests_dir"]),
        source_globs=list(raw["source_globs"]),  # type: ignore[arg-type]
        test_globs=list(raw["test_globs"]),  # type: ignore[arg-type]
    )


def matches_any(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch("/" + path, "*/" + g) for g in globs)


@dataclass
class Node:
    id: str
    title: str
    depends_on: list[str] = field(default_factory=list)
    verified_by: str = ""
    deliverable: str = ""


@dataclass
class Cap:
    cap_id: str
    node: str
    status: str
    proof: str
    note: str


class HarnessError(Exception):
    """Raised when a harness input file is malformed."""


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_graph(text: str) -> dict[str, Node]:
    """Parse every markdown table row whose first cell is a node id (e.g. W0.1, N1.2)."""
    nodes: dict[str, Node] = {}
    in_fence = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not raw.lstrip().startswith("|"):
            continue
        cells = _cells(raw)
        node_id = cells[0].strip("*` ")
        if not NODE_RE.match(node_id):
            if NODE_LIKE_RE.match(node_id):
                raise HarnessError(f"graph line {lineno}: malformed node id {node_id!r}")
            continue
        if len(cells) < 3:
            raise HarnessError(f"graph line {lineno}: node {node_id} row needs a depends_on cell")
        if node_id in nodes:
            raise HarnessError(f"duplicate node {node_id} in graph")
        deps: list[str] = []
        if cells[2] not in ("", "—", "-"):
            for part in cells[2].split(","):
                dep = part.strip().strip("*` ")
                if not NODE_RE.match(dep):
                    raise HarnessError(f"{node_id}: unparseable depends_on entry {part.strip()!r}")
                deps.append(dep)
        nodes[node_id] = Node(
            id=node_id,
            title=cells[1],
            depends_on=deps,
            verified_by=cells[3] if len(cells) > 3 else "",
            deliverable=cells[4] if len(cells) > 4 else "",
        )
    if not nodes:
        raise HarnessError("graph has no node rows")
    return nodes


def load_graph(cfg: Config) -> dict[str, Node]:
    return parse_graph(cfg.graph.read_text(encoding="utf-8"))


def parse_catalog(text: str) -> list[Cap]:
    rows = list(csv.reader(text.splitlines(), delimiter="\t"))
    if not rows or tuple(c.strip() for c in rows[0]) != CATALOG_FIELDS:
        raise HarnessError("catalog header must be exactly: " + " | ".join(CATALOG_FIELDS))
    caps: list[Cap] = []
    seen: set[str] = set()
    for i, row in enumerate(rows[1:], start=2):
        if not row or all(not c.strip() for c in row):
            continue
        if len(row) != len(CATALOG_FIELDS):
            raise HarnessError(f"catalog line {i}: expected 5 columns, got {len(row)}")
        cap_id, node, status, proof, note = (c.strip() for c in row)
        if not cap_id or not node:
            raise HarnessError(f"catalog line {i}: cap_id and node are required")
        if status not in STATUSES:
            raise HarnessError(f"catalog line {i}: unknown status {status!r}")
        if cap_id in seen:
            raise HarnessError(f"catalog line {i}: duplicate cap {cap_id}")
        seen.add(cap_id)
        caps.append(Cap(cap_id=cap_id, node=node, status=status, proof=proof, note=note))
    return caps


def load_catalog(cfg: Config) -> list[Cap]:
    return parse_catalog(cfg.catalog.read_text(encoding="utf-8"))


def write_catalog(caps: list[Cap], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(CATALOG_FIELDS)
        for c in caps:
            writer.writerow([c.cap_id, c.node, c.status, c.proof, c.note])


def node_status(node_id: str, caps: list[Cap]) -> str:
    """green if every row is green; building if any row is building or green;
    otherwise spec if any row is spec, else not-started."""
    rows = [c for c in caps if c.node == node_id]
    if not rows:
        return "not-started"
    statuses = {c.status for c in rows}
    if statuses == {"green"}:
        return "green"
    if statuses & {"building", "green"}:
        return "building"
    if "spec" in statuses:
        return "spec"
    return "not-started"


def find_cycle(nodes: dict[str, Node]) -> list[str] | None:
    """Return one dependency cycle as a list of node ids, or None."""
    white, grey, black = 0, 1, 2
    color = dict.fromkeys(nodes, white)
    stack: list[str] = []

    def visit(n: str) -> list[str] | None:
        color[n] = grey
        stack.append(n)
        for d in nodes[n].depends_on:
            if d not in nodes:
                continue
            if color[d] == grey:
                return [*stack[stack.index(d) :], d]
            if color[d] == white:
                found = visit(d)
                if found:
                    return found
        stack.pop()
        color[n] = black
        return None

    for n in nodes:
        if color[n] == white:
            found = visit(n)
            if found:
                return found
    return None


def eligibility_problems(
    nodes: dict[str, Node], caps: list[Cap], simulate_start: str | None = None
) -> list[str]:
    """Every reason the graph is not eligible. An empty list means eligible."""
    problems: list[str] = []
    for n in nodes.values():
        for d in n.depends_on:
            if d not in nodes:
                problems.append(f"{n.id} depends on unknown node {d}")
    cycle = find_cycle(nodes)
    if cycle:
        problems.append("dependency cycle: " + " -> ".join(cycle))
    for c in caps:
        if c.node not in nodes:
            problems.append(f"catalog row {c.cap_id} names unknown node {c.node}")
    for n in nodes.values():
        status = node_status(n.id, caps)
        if not (status in ("building", "green") or n.id == simulate_start):
            continue
        for d in n.depends_on:
            if d in nodes and node_status(d, caps) != "green":
                problems.append(
                    f"{n.id} is {'starting' if n.id == simulate_start else status} "
                    f"but dependency {d} is {node_status(d, caps)}"
                )
    return problems


def spec_dir(node_id: str, specs: Path) -> Path | None:
    matches = sorted(specs.glob(f"{node_id}-*"))
    return matches[0] if matches else None
