# {{node}} tasks

1. Write the failing tests for each proof dimension.
2. Build until they pass.
3. Run `python3 harness/node_converge.py {{node}}` until it passes.
4. Hand off to the verifier; fix what it confirms.
5. Flip the rows green with their proofs, add the changelog entry, commit.
