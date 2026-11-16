---
name: record-decision
description: Record a decision in docs/decisions.md with the next free D-number, its context, options, the strongest argument against it, and what would reopen it. Use when the user or an agent settles a question that future sessions must not re-ask.
argument-hint: "<the decision in a sentence>"
---

1. Search `docs/decisions.md` for the topic first. If a decision already covers it, cite that number instead of writing a new one, or write a new entry that explicitly supersedes it.
2. Find the next free number: the last `## D-<n>` in the file, plus one; confirm `git log --all --oneline -S"## D-<n>"` finds nothing, so parallel branches never collide.
3. Append, newest last:
   ```
   ## D-<n>: <title>

   **Date:** <YYYY-MM-DD> · **Decided by:** <owner | engineering-manager | ...>

   **Trigger:** "<the question, quoted>"
   **Context:** <evidence: files, ids, counts>
   **Options:** <what was considered>
   **Decision:** <an instruction someone can follow without this conversation>
   **Strongest argument against:** <...>
   **Why it loses:** <...>
   **Reopen if:** <...>
   ```
4. If the decision is a rule that must hold on every turn, propose adding one line to `docs/standing-principles.md` citing the number (keep that file under 25 lines).
