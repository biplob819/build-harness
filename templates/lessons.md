# Lessons

<!-- One entry per mistake that reached review. Say what happened, why, and the control that now prevents it (a gate, a test, a principle). A lesson without a control is a wish. -->

## L-1: (example) A test passed because it was skipped

**What happened:** A row flipped green while its proof test carried a skip marker.
**Why:** Nothing checked that a cited test actually runs.
**Control:** `node_converge.py` gate `proofs` fails any skipped test it is pointed at.
