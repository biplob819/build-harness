---
name: record-lesson
description: Turn a mistake that reached review into a lesson with a control - a gate, a test or a standing principle - so it cannot happen again. Use after a verifier finding, a failed deploy, a reverted change, or whenever the user says "remember this" about a mistake.
argument-hint: "<what went wrong>"
---

1. Find the root cause, not the symptom: why did nothing catch it before review?
2. Append to `docs/lessons.md` with the next `L-<n>`: what happened, why, and the control that now prevents it.
3. Pick the strongest control that fits, in this order:
   - **A gate** if the mistake can be detected mechanically: use the add-gate skill.
   - **A test** if it is about one behaviour.
   - **A standing principle** if it is a judgement rule (record a decision first and cite it).
4. A lesson with no control is a wish: say so plainly if you could not find one, and ask the user.
