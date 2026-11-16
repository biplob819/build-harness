# Build graph

Source of truth for build-node dependencies. A node may start only when every node in its `Depends on` cell is green (all its rows in `catalog.tsv` are green). No cycles.

| Node | Title | Depends on | Verified by | Deliverable |
| --- | --- | --- | --- | --- |
| **W0.1** | Repository and harness | — | node_converge + verifier | Repo, CI, the harness scripts with self-tests, decisions and lessons files |
| **N1.1** | First capability | W0.1 | node_converge + verifier | Replace with your first real slice of the product |
