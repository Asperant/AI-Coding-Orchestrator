# Test Scenarios Template

Bu şablon, bir projede tekrar tekrar kontrol edilmesi gereken test senaryolarını tutmak için kullanılır.

Amaç:
AI’ın her kod değişikliğinde sadece happy path düşünmesini engellemek; proje özel edge case, regression ve riskli akışları hatırlamasını sağlamaktır.

Bir projede bu şablondan üretilen dosya genelde şu konumda tutulur:

```text
docs/test-scenarios.md
```

---

## 1. How to use

Her test senaryosu şu formatta kaydedilir:

```text
Scenario:
Category:
Related flow:
Related files:
Steps:
Expected result:
Failure signs:
Priority:
```

Priority değerleri:

```text
critical
high
medium
low
```

---

## 2. Core smoke tests

### App opens

Scenario:

```text
User opens the app successfully.
```

Steps:

```text
1. Start the app.
2. Open the home screen.
3. Confirm there is no crash.
```

Expected result:

```text
The app opens and initial UI is usable.
```

Priority:

```text
critical
```

---

### Main user flow

Scenario:

```text
User can complete the main product flow.
```

Steps:

```text
1. Start from home.
2. Continue through the main flow.
3. Complete the core action.
4. Reach the final/result state.
```

Expected result:

```text
The main flow completes without blocking errors.
```

Priority:

```text
critical
```

---

## 3. Common edge case tests

### Empty state

Scenario:

```text
The app handles missing or empty data.
```

Steps:

```text
1. Simulate empty data.
2. Open the relevant screen.
```

Expected result:

```text
The UI shows a useful empty state instead of breaking.
```

Priority:

```text
high
```

---

### Error state

Scenario:

```text
The app handles an expected error.
```

Steps:

```text
1. Simulate an API/server/service error.
2. Trigger the affected flow.
```

Expected result:

```text
The UI shows an understandable error state and recovery option if possible.
```

Priority:

```text
high
```

---

### Network/server failure

Scenario:

```text
The app handles unavailable network or backend.
```

Steps:

```text
1. Stop the backend or disconnect network.
2. Trigger the affected flow.
```

Expected result:

```text
The app does not crash and shows fallback/retry behavior.
```

Priority:

```text
high
```

---

### Rapid repeated action

Scenario:

```text
User taps or submits repeatedly.
```

Steps:

```text
1. Rapidly click/tap the same action multiple times.
2. Observe duplicate submissions or broken state.
```

Expected result:

```text
The app prevents duplicate actions or handles them safely.
```

Priority:

```text
medium
```

---

## 4. AI pipeline tests

### AI service unavailable

Scenario:

```text
AI service is unavailable.
```

Steps:

```text
1. Stop the AI service or backend.
2. Trigger AI-dependent flow.
```

Expected result:

```text
Fallback behavior works and the user is not blocked.
```

Priority:

```text
critical
```

---

### Empty AI response

Scenario:

```text
AI returns empty or malformed response.
```

Steps:

```text
1. Simulate empty or malformed AI response.
2. Trigger result generation.
```

Expected result:

```text
The app handles the response safely and uses fallback if needed.
```

Priority:

```text
critical
```

---

### AI queue/rate-limit behavior

Scenario:

```text
Multiple AI jobs are created close together.
```

Steps:

```text
1. Trigger multiple AI-dependent requests.
2. Observe queue/rate-limit behavior.
```

Expected result:

```text
The app handles queue/rate limits without corrupting user state.
```

Priority:

```text
high
```

---

## 5. Privacy / permission tests

### Permission denied

Scenario:

```text
User denies a sensitive permission.
```

Steps:

```text
1. Deny camera/microphone/location permission if used.
2. Continue the flow.
```

Expected result:

```text
The app explains the state clearly and continues or exits safely.
```

Priority:

```text
high
```

---

### Sensitive data logging

Scenario:

```text
Sensitive user data should not appear in logs.
```

Steps:

```text
1. Trigger sensitive flows.
2. Inspect console/server logs.
```

Expected result:

```text
Logs do not expose secrets, tokens, private user data, or sensitive signals.
```

Priority:

```text
critical
```

---

## 6. Regression tests

Known regression areas:

```text

```

For each new code change, AI should ask:

```text
Does this change touch any known regression area?
```

---

## 7. AI behavior

Before coding, AI should check whether the task touches any known test scenario.

After coding, AI should report:

1. Which scenarios should be tested
2. Which scenarios are critical
3. Which scenarios could not be tested automatically
4. Whether `docs/test-scenarios.md` should be updated

---

## 8. Final rule

A change is stronger when it comes with a test scenario.

If no test is possible, AI must explain why and provide manual verification steps.