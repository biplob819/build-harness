# CLAUDE.md: project constitution

<!-- Build Harness template. Keep it short: rules the agent must follow on every task, each one testable. -->

**Project:** {{project}}
**Owner:** {{owner}}

## Non-negotiable rules

1. Every capability is built node by node: `python3 harness/node_start.py <node>` must say GO before work starts, and `python3 harness/node_converge.py <node>` must PASS before a row flips green.
2. Write the failing test first. A row is green only when every proof dimension cites a real, unskipped test (or `n/a:<reason>` where allowed).
3. Never bypass a gate: no `--no-verify`, no skipped tests to get green, no weakened assertions.
4. Before deciding anything, search `docs/decisions.md` for the topic. A recorded decision binds you; cite its number.
5. Every mistake that reaches review becomes a lesson in `docs/lessons.md`, and, when it can be checked mechanically, a new gate.
6. Never push, merge or touch production, money, credentials or anyone's data without the owner's explicit go.

## Roles

- **builder** builds one node at a time and hands off; never audits its own work.
- **verifier** tries to refute every claim and finding, from a fresh start.
- **engineering-manager** decides the engineering calls the builder or verifier escalate, and records them.
- **The owner** decides scope, anything irreversible, and anything external.

## Where things live

| What | Where |
| --- | --- |
| Build graph (nodes, dependencies) | `docs/graph/graph.md` |
| Capability ledger (status, proofs) | `docs/graph/catalog.tsv` |
| Node specs | `specs/<node>-<slug>/` (spec, criteria, tasks, RUN-STATE) |
| Decisions | `docs/decisions.md` |
| Lessons | `docs/lessons.md` |
| Standing principles (re-read every turn) | `docs/standing-principles.md` |
| Command gates | `harness/gates.tsv` |
