# Standing principles

<!-- Injected into context at session start and on every prompt by the Build Harness hooks. Keep it under 25 lines. Add a rule only with the decision number that settled it. -->

1. Build only the node `node_start.py` says GO for. Nothing builds ahead of a dependency that is not green.
2. Failing test first; green only with proof on every dimension.
3. Never bypass a gate or weaken a test. If a gate is wrong, fix the gate and record why.
4. Search `docs/decisions.md` before asking the owner anything; ask only what it leaves open, with your recommendation first.
5. Engineering calls go to the engineering-manager agent; scope cuts, irreversible changes and anything external go to the owner.
6. Never push, merge or deploy without the owner's go.
