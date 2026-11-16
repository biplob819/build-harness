# Decisions

<!-- One entry per decision, newest last. Read the last entry for the next number; never reuse one. -->

## D-1: Use Build Harness for this repository

**Date:** {{date}} · **Decided by:** owner

**Context:** Agents repeat mistakes and drift without gates and memory.
**Decision:** Build node by node behind `node_start.py` and `node_converge.py`; record decisions here and lessons in `docs/lessons.md`.
**Strongest argument against:** The ceremony slows the first week.
**Why it loses:** Each gate is written once and then runs for free on every node.
**Reopen if:** The gates cost more time than the defects they catch.
