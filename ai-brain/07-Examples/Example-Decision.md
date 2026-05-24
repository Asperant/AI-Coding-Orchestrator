# Example Decision: Local Fallback for AI-Dependent Result Generation

This is a filled example of [[Decision-Template]].

## Decision

When the AI service is unavailable or returns a malformed response, the app will generate results using a local deterministic fallback instead of showing a generic error screen.

## Context

The app depends on an external AI service to generate personalized result text after the user completes a flow. During testing, the AI service occasionally times out, returns empty JSON, or hits rate limits. When this happens, the user sees a broken screen or a generic "something went wrong" message after investing several minutes in the flow. This destroys user trust.

## Options

1. **Show error and ask user to retry.** Simple, but frustrating after a long flow.
2. **Queue the request and poll.** More robust, but adds backend complexity and the user still waits.
3. **Local deterministic fallback.** Generate a reasonable result from the user's answers using templates, without AI. Less personalized, but instant and reliable.
4. **Cached AI responses.** Pre-generate results for common answer patterns. Complex to maintain and doesn't cover edge cases.

## Chosen option

Option 3: Local deterministic fallback.

## Why

- The user should never be blocked after completing a flow.
- A template-based result is better than no result.
- The fallback can be implemented quickly without backend changes.
- AI-generated results can still be used when available; the fallback is a safety net.
- This approach matches the "small safe change" principle.

## Trade-offs

Pros:

- User always gets a result.
- No additional backend infrastructure needed.
- Fallback is testable and predictable.
- Can be shipped independently of AI service improvements.

Cons:

- Fallback results are less personalized than AI-generated ones.
- Two code paths to maintain (AI + fallback).
- Risk of the fallback becoming stale if the result format evolves.

## Risks

- If the AI service is down for an extended period, all users get fallback results. This is acceptable but should be monitored.
- The fallback text quality must match the product tone. Poorly written templates would hurt trust.
- Developers might forget to update fallback templates when the result schema changes.

## Revisit trigger

- If the AI service achieves 99.9% uptime for 3+ months, consider simplifying the fallback.
- If the result schema changes significantly, update fallback templates at the same time.
- If users report that fallback results feel generic, invest in better templates or a hybrid approach.
