---
name: build-node
description: Build one node of the build graph end to end with the Build Harness loop - start check, failing tests first, build, converge, adversarial verification, green with proofs, records, commit. Use when the user says "build N1.2", "next node", or "continue the build".
argument-hint: "<node id, e.g. N1.2>"
---

Node: `$ARGUMENTS` (if empty, pick the first node in `docs/graph/graph.md` whose dependencies are all green and that is not green itself, and confirm it with the user).

1. `python3 harness/node_start.py <node>`. If it does not say GO, stop and report the reasons. Do not build ahead.
2. Delegate the build to the **builder** agent with the node id and its spec folder. The builder writes failing tests first, builds, and runs `python3 harness/node_converge.py <node>` until it passes.
3. Delegate an audit to the **verifier** agent (finder role) for the node's capabilities. Then send each candidate finding to a fresh **verifier** call (verifier role) to refute or confirm it.
4. Confirmed findings go back to the builder as a fix batch, then to the verifier (fix-verifier role). Repeat until nothing confirmed is open.
5. Escalations the builder cannot decide go to the **engineering-manager** agent; anything it returns as `owner-required` comes to the user as one batched question, with the recommendation first.
6. When clean: rows flip green with proofs, `RUN-STATE.md` and `changelog.md` are updated, converge passes once more, and the builder commits. Do not push.
7. Report: what was built, the converge result, findings found and closed, decisions recorded, lessons added, and what is next in the graph.
