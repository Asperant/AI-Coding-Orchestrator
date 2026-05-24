# Example Bug Fix: App Freezes When AI Service Returns Empty Response

This is a filled example of [[Bug-Fix-Template]].

## Bug

The app gets stuck on a loading spinner after the user completes the main flow. The result screen never appears.

## Expected behavior

After the user completes all steps, the app should display a result screen within 15 seconds, either from the AI service or from the local fallback.

## Actual behavior

The app shows a loading spinner indefinitely. The console shows no error. The user has no way to recover without closing the app.

## Error / log

```text
[server] POST /api/ai-jobs 200 — 4212ms
[server] AI response body: {}
[client] ResultScreen mounted, waiting for result...
[client] (no further logs)
```

The server returns HTTP 200 with an empty JSON body `{}`. The client receives a success status but the response contains no usable data. The result parsing code does not handle this case and silently produces `undefined`, which causes the UI to wait forever.

## Root cause

The result parsing function assumes the AI response always contains a `result` key:

```javascript
const output = response.data.result.summary;
```

When `response.data` is `{}`, accessing `.result.summary` throws a TypeError that is caught by a generic try/catch which swallows the error silently. The component remains in loading state because neither the success nor the error path is triggered.

## Fix

Added an explicit check for empty or malformed AI responses before parsing:

```javascript
if (!response.data || !response.data.result) {
  console.warn('AI response empty or malformed, activating fallback');
  return generateLocalFallback(userAnswers);
}
```

Also added a 12-second timeout in the client that triggers the fallback if no valid result arrives.

## Changed files

- `server/index.js` — added empty response validation before returning to client
- `src/services/aiService.js` — added response shape check and fallback trigger
- `src/components/ResultScreen.jsx` — added timeout-based fallback activation

## Test

Manual test steps:

1. Start the app with the AI service running. Complete the flow. Confirm result appears normally.
2. Stop the AI service. Complete the flow. Confirm fallback result appears within 15 seconds.
3. Start the AI service but modify it to return `{}`. Complete the flow. Confirm fallback activates and no spinner gets stuck.
4. Start the AI service but add a 20-second delay. Confirm the client timeout triggers fallback at 12 seconds.

All four scenarios passed.

## Lesson learned

- AI service responses must never be trusted blindly. Always validate response shape before parsing.
- Silent error swallowing (`catch {}`) in async flows is extremely dangerous — it hides bugs and creates zombie loading states.
- Every AI-dependent flow needs both a response validation check and a client-side timeout as independent safety nets.

See also: [[Example-Lesson]]
