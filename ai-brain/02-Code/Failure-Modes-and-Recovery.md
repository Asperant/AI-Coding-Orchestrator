# Failure Modes and Recovery

This file documents common ways the AI engineering system can fail and how to recover.

---

## 1. AI edits too many files

Symptom: The diff contains changes to 5+ files, many unrelated to the task.

Why it is bad: Large diffs are hard to review, hide bugs, and increase regression risk. They violate the "small scoped change" principle.

Recovery: Reject the change. Ask AI to identify only the files necessary for the task. Resubmit with a tighter scope. Use [[Pre-Flight-Checklist]] to enforce scope before coding.

Prevention: Always require a plan before implementation. The plan must list expected files to change. If the actual diff exceeds the plan, stop.

---

## 2. AI skips planning

Symptom: AI jumps directly to writing code without inspecting files, classifying the task, or proposing a plan.

Why it is bad: Without a plan, AI may misunderstand the task, touch the wrong files, or break existing behavior.

Recovery: Stop the implementation. Ask AI to classify the task type, inspect relevant files, and propose a plan first.

Prevention: Use [[Codex-Task-Prompt]] or [[Elite-Coding-Workflow]], which require plan-before-code. Start every session with [[CORE-RULES]].

---

## 3. AI ignores task type classification

Symptom: AI treats every task as a generic feature. It does not consider security, database, or AI pipeline risks even when the task touches those areas.

Why it is bad: Different task types have different risks. A database change without migration awareness can corrupt data. A security change without auth checks can expose user data.

Recovery: Explicitly ask AI to classify the task using [[Task-Type-Rules]]. If it missed a risk, ask it to re-review with the correct task type.

Prevention: Include task type classification as the first step in every coding workflow.

---

## 4. AI misses security or privacy risk

Symptom: Code change touches auth, user data, secrets, database rules, or permissions, but the AI does not mention any risk.

Why it is bad: Security issues in production are expensive and trust-destroying.

Recovery: Run a focused security review using the Security Agent lens or [[Code-Review-Prompt]] with explicit focus on auth, data access, and secrets.

Prevention: [[Task-Type-Rules]] defines a priority order where security is always first. If a task touches any of: auth, payment, database, user data, camera, secrets — security review is mandatory.

---

## 5. AI confuses active and legacy code paths

Symptom: AI modifies or references an old endpoint, service, or file that is no longer active. Or AI creates a new path that duplicates an existing active one.

Why it is bad: Legacy code confusion creates bugs that are hard to trace and wastes time on dead code.

Recovery: Check the project's `AGENTS.md` and `docs/project-map.md` for the currently active paths. Correct the AI and re-apply the change to the right files.

Prevention: Good `AGENTS.md` and `docs/project-map.md` files should explicitly list active paths and warn about legacy ones. See [[Example-Project-Map]] for reference.

---

## 6. AI produces overly verbose output

Symptom: AI returns pages of explanation when a short answer would suffice. Review reports repeat the same points. Plans contain unnecessary theory.

Why it is bad: Verbose output wastes time, obscures important findings, and exhausts context windows.

Recovery: Ask AI to summarize findings in bullet points. Request "short answer only" or "list the changes, risks, and test steps — nothing else."

Prevention: Prompts should specify expected output format and length. Include constraints like "answer in under 200 words" when appropriate.

---

## 7. AI adds unnecessary abstractions

Symptom: AI introduces new layers, wrapper functions, abstract classes, or utility modules that the project does not need.

Why it is bad: Unnecessary abstractions increase maintenance cost, hide logic, and make code harder to understand.

Recovery: Reject the abstraction. Ask AI to implement the same behavior with the simplest possible approach. Reference existing code style.

Prevention: [[My-AI-Coding-Rules]] and [[CORE-RULES]] both state: no unnecessary abstractions. Reinforce this in the task prompt.

---

## 8. AI does not update memory or docs

Symptom: A significant decision, bug fix, or lesson is discovered during coding, but AI does not suggest saving it. The knowledge disappears when the chat ends.

Why it is bad: Lost knowledge means repeating mistakes. The AI-Brain stays empty despite real work being done.

Recovery: At the end of each significant task, explicitly ask: "Was a decision, bug fix, or lesson discovered? Should anything be saved to AI-Brain or project docs?"

Prevention: [[Post-Flight-Review]] and [[Project-Memory-Sync-Rules]] include a memory sync check. Make it a habit to run this step.

---

## 9. AI repeats rules instead of applying them

Symptom: AI quotes the workflow rules, checklists, or task type definitions back to you instead of actually performing the work according to those rules.

Why it is bad: Reciting rules is not the same as following them. The user wants results, not a policy document.

Recovery: Tell AI: "Do not quote the rules. Apply them to this specific task and give me the result."

Prevention: Prompts should ask for concrete output (plan, diff, test steps), not ask AI to describe what it would do.

---

## 10. User request is ambiguous

Symptom: AI makes assumptions about the task that don't match what the user intended. Implementation goes in the wrong direction.

Why it is bad: Wasted effort, wrong code, potential damage to existing behavior.

Recovery: AI should ask clarifying questions before proceeding. If AI already implemented something wrong, revert and restart with a clear task definition.

Prevention: [[CORE-RULES]] states: "If uncertain, state your assumption explicitly." Train this behavior by rejecting outputs that made silent assumptions.

---

## 11. Multi-agent review produces noise instead of a decision

Symptom: The orchestrator output contains long agent reports but no clear final decision. The user reads pages of analysis but does not know what to do next.

Why it is bad: The point of multi-agent review is to reduce noise, not add it. A review without a decision is useless.

Recovery: Ask for the consolidated output only: decision, required fixes, recommended tests, one next action. Ignore individual agent reports unless needed for detail.

Prevention: Use [[Multi-Agent-Review-Template]] which ends with: Final Decision, Required Fixes, One Small Next Action. See [[Example-Multi-Agent-Review]] for correct output.
