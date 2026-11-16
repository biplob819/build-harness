---
name: add-gate
description: Add a new Build Harness gate - a command gate in harness/gates.tsv, or a small check script - with proof that it fails on the mistake it exists for. Use when a lesson can be checked mechanically, or the user asks to enforce something on every push or converge.
argument-hint: "<what the gate must catch>"
---

1. Prefer the simplest form: a command that exits non-zero on the mistake. Add a row to `harness/gates.tsv`: `name<TAB>when<TAB>command`, with `when` = `converge`, `pre-push` or `both`. Use `pre-push` or `both` only for checks fast enough to run on every push.
2. If no existing tool can detect it, write a script under `harness/` (for example `harness/check_<name>.py`) that prints what it found and exits 1, with a `--self-test` flag that plants the mistake in a temp directory and proves the check catches it, and that a clean case passes.
3. Prove the gate can fail: plant the mistake, run `python3 harness/node_converge.py <node>` (or `--pre-push`), and show the FAIL. Then remove it and show the PASS.
4. Record why the gate exists: cite the lesson (`L-<n>`) or decision (`D-<n>`) in a `#` comment line just above the gates.tsv row, or at the top of the script.
