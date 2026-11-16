---
name: init
description: Install Build Harness into the current repository: harness scripts, constitution, standing principles, decision and lesson logs, build graph, capability catalog, command gates, the first node's spec, and a git pre-push hook. Use when the user asks to set up, install or initialise Build Harness. Never overwrites existing files.
argument-hint: "[--stack python|node|go|none]"
---

1. Find the plugin root: the session context has a line `Build Harness plugin root: <path>`. If it is missing, ask the user where they cloned build-harness.
2. Show the user what will be written first:
   `python3 "<plugin root>/scripts/init.py" "$CLAUDE_PROJECT_DIR" --dry-run $ARGUMENTS`
3. Run it for real without `--dry-run`. It never overwrites a file; report anything it left as is.
4. Read the new `docs/graph/graph.md` and `docs/graph/catalog.tsv` with the user and help replace the example nodes with their product's real slices: small nodes, explicit dependencies, one row per capability.
5. Check `harness/gates.tsv` matches how this project lints, type-checks, tests and builds. Each row: `name<TAB>when<TAB>command`, where `when` is `converge`, `pre-push` or `both`.
6. Run the self-tests to prove the install: `python3 harness/node_start.py --self-test`, `python3 harness/node_converge.py --self-test`, `python3 harness/secret_scan.py --self-test`.
7. Suggest committing the harness as node W0.1 using the build-node skill.
