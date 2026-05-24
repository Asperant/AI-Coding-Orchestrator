# Archive and Merge Recommendations

This file records future cleanup recommendations only.

No archive, merge, delete, move, or rename action has been applied.

## Recommended review items

| Files | Suggested future action | Reason | Risk of changing | Recommended timing |
|------|--------------------------|--------|------------------|--------------------|
| `Codex-Workflow.md` + `Codex-Workflow-Summary.md` | Consider keeping one primary doc and archiving or clearly narrowing the other | Likely overlap between full and condensed workflow guidance | Medium: existing wiki links or preferred reading habits may break | Next documentation audit |
| `Global-AI-Profile.md` + `My-AI-Coding-Rules.md` + `CORE-RULES.md` | Consider a future overlap audit and possible consolidation plan | Core identity and coding-rule content may drift over time | High: these are onboarding-critical files | Only after a careful cross-link and usage audit |
| `Code-Review-Prompt.md` + `Codex-Diff-Review-Prompt.md` + `Run-Multi-Agent-Diff-Review.md` | Consider clarifying ownership or reducing overlap between review prompts | There are now multiple review-entry documents with related purpose | Medium: different tools may rely on different prompt styles | After practical usage patterns are clearer |
| `Orchestrator-Agent.md` + `Orchestrator-Workflow.md` + `Run-Orchestrated-Coding-Task.md` | Consider documenting a clearer conceptual vs practical split, then archive overlap if needed | V4 now has both architecture docs and a practical run prompt | Medium: V4 onboarding could become less clear if changed too early | After more real-world orchestrator usage |
| `Example-Decision.md` + `Real-Decision-AI-Brain-Global-vs-Project-Docs.md` | Consider separating example-only vs real-decision usage more explicitly | Both are decision-shaped documents but serve different roles | Low to medium: mostly classification and expectation risk | After `06-Decisions` starts being used |
| `README-FOR-AI.md` + `Home.md` | Consider a future responsibility split audit | Both act as entry/navigation surfaces and may accumulate duplicate links | Medium: they are primary onboarding files | Later, after the structure stabilizes |

## Recommendation rule

Before any cleanup is applied in the future:

1. Check wiki links.
2. Check whether a file is onboarding-critical.
3. Decide whether the change is archive-only, merge, or just better cross-linking.
4. Apply changes only as a separate approved cleanup task.
