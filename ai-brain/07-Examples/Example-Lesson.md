# Example Lesson: AI Pipeline Changes Need Fallback and Malformed Response Tests

This is a filled example of the format used in [[Lessons-Learned]].

---

### 2026-05-15 — AI pipeline changes must always include fallback and malformed response tests

## Context

While working on an AI-dependent result generation feature, the AI service started returning empty responses during high load. The app showed an infinite loading spinner with no error message. The bug was hard to reproduce because it only happened under specific timing conditions.

## Lesson

Any change to an AI pipeline — prompt changes, model changes, endpoint changes, queue changes, fallback changes — must be tested against these scenarios before the change is considered complete:

1. **AI service unavailable** — server is down or unreachable.
2. **AI service returns empty response** — HTTP 200 but body is `{}` or `null`.
3. **AI service returns malformed response** — unexpected schema, missing fields, wrong types.
4. **AI service times out** — response takes longer than the client timeout.
5. **AI service returns error** — HTTP 4xx or 5xx with or without error body.
6. **Rapid repeated requests** — user triggers the same AI call multiple times quickly.

If any of these scenarios is not tested, the change is not complete.

## Use later

- Add these 6 scenarios to the project's `docs/test-scenarios.md` AI pipeline section.
- Reference this lesson in [[Pre-Flight-Checklist]] when the task type is "AI pipeline change."
- Use this as a mental checklist before approving any AI-related diff.
- This applies to every project that depends on an external AI or LLM service, not just the current one.
