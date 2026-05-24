# Example Multi-Agent Review: AI Result Flow Fallback Diff

This is a filled example of [[Multi-Agent-Review-Template]].

---

## Request

Add a local fallback for the AI result generation flow so the user is never stuck on a loading screen when the AI service fails.

---

## Task Type

AI pipeline change + UI change

---

## Agents Used

- [x] Planner Agent
- [x] Coder Agent
- [x] Reviewer Agent
- [x] Security Agent
- [x] Tester Agent
- [ ] Architect Agent
- [x] Product Agent
- [ ] Release Agent

---

## Agent Findings

### Planner Agent

```text
Task: Add fallback result generation when AI service fails or returns empty/malformed response.
Type: AI pipeline change (primary), UI change (secondary).
Files to inspect: src/services/aiService.js, server/index.js, src/components/ResultScreen.jsx.
Files to change: same three files.
Risk: fallback quality, silent error swallowing, timeout race condition.
Plan: 1) Add response validation in server. 2) Add fallback trigger in aiService. 3) Add timeout in ResultScreen.
```

### Coder Agent

```text
Changed files:
- server/index.js — added empty response check before returning AI result
- src/services/aiService.js — added response shape validation, fallback trigger
- src/components/ResultScreen.jsx — added 12s timeout, fallback activation on timeout

What changed: Three-layer safety net: server validates, service falls back, UI times out.
Risk: Two code paths (AI + fallback) to maintain.
```

### Reviewer Agent

```text
Good:
- Change is small and scoped to three files.
- Each layer has independent safety check.
- No unrelated files changed.

Needs improvement:
- The timeout value (12s) is hardcoded. Consider extracting to config.
- console.warn is used but no structured logging.

Bugs / edge cases:
- If the fallback itself throws, the catch block shows a generic error. Add a safe fallback-of-fallback.

Decision: Approved with changes
```

### Security Agent

```text
Security summary:
- No secret/token exposure.
- No user data logged in the new code paths.
- AI response is validated before being passed to the UI — good.

Privacy/data risks:
- Fallback uses only user answers already in client memory — no new data exposure.

AI/fallback/logging risks:
- console.warn includes the AI response status but not the response body. This is correct — do not log the body as it could contain user-related content.

Decision: Approved
```

### Tester Agent

```text
Critical manual tests:
1. AI service running, normal flow → result appears from AI.
2. AI service stopped → fallback result appears within 15s.
3. AI service returns {} → fallback activates, no spinner.
4. AI service delays 20s → client timeout at 12s, fallback activates.
5. Rapid submit during loading → no duplicate results or state corruption.

Regression risks:
- Existing result scoring logic must still work with AI-generated results.

Suggested automated tests:
- Unit test for response shape validation function.
- Integration test for fallback trigger on empty response.

Decision: Approved with changes (add test for rapid submit scenario)
```

### Product Agent

```text
Product summary:
- User experience improved: no more stuck screens.
- Fallback text should match the product tone: neutral, non-clinical, non-judgmental.

Copy / tone concerns:
- Fallback result text must be reviewed for tone. Generic template language like "Your results are ready" is acceptable. Avoid clinical or diagnostic framing.

Decision: Approved with changes (review fallback copy)
```

---

## Consolidated Risks

```text
1. Hardcoded 12s timeout — should be configurable.
2. Fallback-of-fallback not handled — if local generation throws, user sees generic error.
3. Fallback copy must match product tone — needs product review.
4. Two code paths to maintain — fallback templates must stay in sync with result schema.
```

---

## Required Fixes

```text
1. Extract timeout value to a constant or config.
2. Add safe wrapper around fallback generation.
3. Review fallback result copy for product tone.
```

---

## Recommended Tests

```text
1. AI service running → normal result.
2. AI service stopped → fallback result.
3. AI returns {} → fallback activates.
4. AI delays 20s → client timeout triggers fallback.
5. Rapid submit → no duplicate results.
6. Fallback itself throws → user sees a graceful error, not a crash.
```

---

## Documentation / Memory Updates

Should anything be saved?

- [x] AI-Brain
- [x] Project docs
- [ ] Both
- [ ] No

Details:

```text
AI-Brain: Save lesson about AI pipeline fallback testing requirements.
Project docs: Update docs/risk-registry.md with "AI fallback failure" risk. Update docs/test-scenarios.md with the 6 test scenarios above.
```

---

## Final Decision

Decision:

```text
Approved with changes
```

---

## One Small Next Action

```text
Extract the 12s timeout to a named constant, add a try/catch around fallback generation, then re-run the 6 manual tests.
```
