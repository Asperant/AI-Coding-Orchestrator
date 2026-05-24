# Quality Gates Template

Bu şablon, bir projede kod değişikliğinin tamamlanmış sayılmadan önce geçmesi gereken kalite kontrollerini tanımlar.

Amaç:
AI’ın sadece kod yazmasını değil; yazdığı kodun build, test, lint, review ve ürün kalite kontrollerinden geçmesini sağlamaktır.

Bir projede bu şablondan üretilen dosya genelde şu konumda tutulur:

```text
docs/quality-gates.md
```

---

## 1. Project commands

Bu projede kalite kontrol için kullanılan komutlar.

### Install

```bash

```

### Development

```bash

```

### Lint

```bash

```

### Typecheck

```bash

```

### Test

```bash

```

### Build

```bash

```

---

## 2. Required gates before completion

Bir kod görevi tamamlandı sayılmadan önce mümkünse şunlar kontrol edilir:

- [ ] Relevant files were inspected before editing
- [ ] Change is small and scoped
- [ ] No unrelated files were changed
- [ ] Lint passes or reason is documented
- [ ] Typecheck passes or reason is documented
- [ ] Tests pass or reason is documented
- [ ] Build passes or reason is documented
- [ ] Manual test steps are provided
- [ ] Diff review is completed
- [ ] [[Definition-of-Done]] is satisfied

---

## 3. Manual test gates

Her önemli değişiklikten sonra manuel kontrol alanları:

- [ ] Happy path
- [ ] Error path
- [ ] Empty/null state
- [ ] Loading state
- [ ] Rapid repeated action
- [ ] Network/server failure
- [ ] Permission denied
- [ ] Regression risk

---

## 4. Risk-specific gates

### Auth / user data

- [ ] User cannot access another user's data
- [ ] Session behavior is correct
- [ ] Unauthorized state is handled
- [ ] Sensitive data is not logged

### Database / storage

- [ ] Migration impact is documented
- [ ] Rollback risk is documented
- [ ] Index need is considered
- [ ] Access rules are considered

### AI pipeline

- [ ] Active AI path is confirmed
- [ ] Fallback behavior is tested
- [ ] Timeout behavior is considered
- [ ] Queue/rate-limit behavior is considered
- [ ] Empty or malformed AI response is handled

### UI / product flow

- [ ] Loading state is visible
- [ ] Error state is understandable
- [ ] Empty state is useful
- [ ] Copy matches product tone
- [ ] Mobile layout is checked

### Privacy / camera / microphone

- [ ] Permission request is clear
- [ ] Permission denied path works
- [ ] User trust risk is considered
- [ ] Data minimization is considered

---

## 5. Completion rule

A change is not complete just because the code was written.

It is complete only when:

```text
The change is scoped, reviewed, tested or testable, and risks are documented.
```

---

## 6. AI behavior

When AI finishes a coding task, it should report:

1. Which gates were checked
2. Which gates could not be checked
3. Why they could not be checked
4. What the user should manually verify
5. Whether the task satisfies [[Definition-of-Done]]