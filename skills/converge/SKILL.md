---
name: converge
description: Run every Build Harness gate for a node and explain the result - which gates failed, why, and the fix for each. Use when the user asks to check, converge, or see whether a node is ready to go green.
argument-hint: "<node id>"
---

1. Run `python3 harness/node_converge.py $ARGUMENTS`. It runs every gate and reports all of them, even after a failure.
2. For each FAIL, say what it means and the real fix:
   - **claims-work**: no row is building; run `node_start.py <node> --mark-building`.
   - **eligibility**: something builds ahead of a dependency that is not green, or the graph has a cycle.
   - **proofs**: a green row cites a missing, renamed or skipped test, or uses n/a where it may not.
   - **secrets**: something looks like a credential. Remove it and rotate it; never mark a real key as allowed.
   - **command gates** (lint, types, tests, build): fix the code, not the gate.
   - **changed-tests**: source changed but no test did; add the test that covers the change.
   - **records**: add the `[<node>]` changelog entry, cover every capability id in `criteria.md`, write `RUN-STATE.md`.
3. Never suggest weakening a test, skipping one, or editing a gate to get to PASS. If a gate is wrong, say why and route it to the engineering-manager agent.
4. Logs are kept in `.harness/<node>/`.
