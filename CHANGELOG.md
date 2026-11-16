# Changelog

## 0.1.0 (2026-11-16)

First public release, extracted from the harness used to build Kova, Insightsflow and eight public AI projects.

- Build graph and capability catalog with `node_start.py` (dependency gate) and `node_converge.py` (claims-work, eligibility, proofs, secrets, command gates, changed-tests, records), each with a `--self-test`.
- Configurable command gates (`harness/gates.tsv`) and settings (`harness.toml`).
- Claude Code plugin: builder, verifier and engineering-manager agents; init, build-node, converge, record-decision, record-lesson and add-gate skills; hooks that inject standing principles and guard `git push`.
- `scripts/init.py` installer and `scripts/evidence.py` for reproducible field numbers.
