# Risk Registry Template

Bu şablon, bir projedeki teknik, ürün, güvenlik, veri ve operasyon risklerini takip etmek için kullanılır.

Amaç:
AI’ın kod yazarken sadece istenen değişikliğe değil, projenin riskli bölgelerine de dikkat etmesini sağlamaktır.

Bir projede bu şablondan üretilen dosya genelde şu konumda tutulur:

```text
docs/risk-registry.md
```

---

## 1. How to use

Her risk şu formatta kaydedilir:

```text
Risk:
Category:
Impact:
Likelihood:
Related files:
How to test:
Mitigation:
Status:
```

Status değerleri:

```text
open
watching
mitigated
accepted
```

---

## 2. Risk categories

- product
- architecture
- security
- privacy
- database
- AI pipeline
- frontend state
- backend
- performance
- release
- legacy code
- testing

---

## 3. Current risks

### Risk 1

Risk:

```text

```

Category:

```text

```

Impact:

```text

```

Likelihood:

```text

```

Related files:

```text

```

How to test:

```text

```

Mitigation:

```text

```

Status:

```text

```

---

### Risk 2

Risk:

```text

```

Category:

```text

```

Impact:

```text

```

Likelihood:

```text

```

Related files:

```text

```

How to test:

```text

```

Mitigation:

```text

```

Status:

```text

```

---

## 4. AI behavior

Before coding, AI should check whether the task touches any known risk.

After coding, AI should report:

1. Which risks were affected
2. Whether any new risk was discovered
3. Whether `docs/risk-registry.md` should be updated
4. How the affected risk should be tested

---

## 5. Common high-risk examples

### User data exposure

Category:

```text
security / privacy
```

Watch for:

```text
auth, database rules, client-side assumptions, logs
```

---

### AI fallback failure

Category:

```text
AI pipeline
```

Watch for:

```text
server unavailable, timeout, empty response, malformed response, queue/rate-limit behavior
```

---

### Camera or microphone trust risk

Category:

```text
privacy / product
```

Watch for:

```text
permission copy, denied path, data minimization, user trust
```

---

### Legacy code path confusion

Category:

```text
legacy code / architecture
```

Watch for:

```text
old service names, inactive endpoints, duplicated flow, outdated docs
```

---

### Over-broad refactor

Category:

```text
architecture / testing
```

Watch for:

```text
large diffs, unrelated files, behavior changes hidden inside refactor
```

---

## 6. Final rule

A risk does not need to block every change.

But if a task touches a known risk area, AI must mention it and suggest how to test it.