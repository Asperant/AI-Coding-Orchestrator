# Project Memory Sync Rules

Bu dosya, AI-Brain ile proje içi dokümantasyon arasındaki bilgi akışını tanımlar.

Amaç:
AI’ın öğrendiği bilgileri doğru yere kaydetmesini sağlamak; global bilgi ile proje özel bilgiyi karıştırmamaktır.

---

## 1. Memory locations

### AI-Brain

Global ve tekrar kullanılabilir bilgiler burada tutulur.

Örnek:

- genel promptlar
- genel checklistler
- AI çalışma kuralları
- kodlama prensipleri
- tekrar kullanılabilir bug dersleri
- genel mimari notları
- kişisel çalışma tercihleri
- agent rolleri
- workflow kuralları

Konum:

```text
/home/asrin/Desktop/AI-Brain
```

---

### Project docs

Proje özel bilgiler repo içindeki `docs/` klasöründe tutulur.

Örnek:

- proje mimarisi
- proje haritası
- proje özel riskler
- proje özel test senaryoları
- proje özel teknik kararlar
- proje özel bug kayıtları
- proje özel release notları
- proje özel legacy alanlar

Konum:

```text
repo/docs/
```

---

## 2. What goes to AI-Brain?

Aşağıdaki bilgi türleri AI-Brain’e kaydedilmelidir:

### Reusable workflow knowledge

Örnek:

```text
AI should always classify coding tasks before implementation.
```

### General prompt templates

Örnek:

```text
A reusable security review prompt.
```

### General checklists

Örnek:

```text
Pre-flight checklist for any coding task.
```

### Personal preferences

Örnek:

```text
I prefer small, practical steps and minimal safe changes.
```

### Cross-project lessons

Örnek:

```text
For AI pipeline features, fallback behavior should always be tested.
```

---

## 3. What goes to project docs?

Aşağıdaki bilgi türleri proje içi `docs/` klasörüne kaydedilmelidir:

### Project-specific architecture

Örnek:

```text
This project uses React + Vite frontend and Express backend.
```

### Project-specific file maps

Örnek:

```text
AI result flow lives in src/services/geminiService.js and server/index.js.
```

### Project-specific risks

Örnek:

```text
Legacy /api/ai-json should not be assumed active.
```

### Project-specific tests

Örnek:

```text
Ollama unavailable fallback must be tested before release.
```

### Project-specific decisions

Örnek:

```text
We use /api/ai-jobs as the current AI path.
```

### Project-specific bugs

Örnek:

```text
Result screen freezes when AI job returns empty response.
```

---

## 4. Sync rule

When a task produces reusable knowledge, AI should ask:

```text
Should this be saved to AI-Brain, project docs, or both?
```

Use this decision rule:

```text
Reusable across projects -> AI-Brain
Specific to one repository -> project docs
Both reusable and project-specific -> save summary to AI-Brain and details to project docs
```

### Decision records note

- AI-Brain-level cross-project decisions should be saved under `06-Decisions/`. See [[Decisions-README]].
- Project-specific decisions should be saved in each project's `docs/decisions/`.
- Generic filled examples of decisions belong in `07-Examples/`, for example [[Real-Decision-AI-Brain-Global-vs-Project-Docs]].
- If a decision is both reusable and project-specific, save a short generalized decision in `06-Decisions/` and the detailed repository context in `docs/decisions/`.
- Use [[Decision-Template]] when creating a new decision record.

---

## 5. After coding

After a coding task, AI should check:

- [ ] Was a technical decision made?
- [ ] Was a bug root cause discovered?
- [ ] Was a new project risk discovered?
- [ ] Was a new test scenario discovered?
- [ ] Was a reusable prompt/checklist/workflow improved?
- [ ] Should AGENTS.md be updated?
- [ ] Should docs/project-map.md be updated?
- [ ] Should docs/risk-registry.md be updated?
- [ ] Should docs/test-scenarios.md be updated?
- [ ] Should AI-Brain Lessons Learned be updated?

---

## 6. Examples

### Example 1

A general rule is discovered:

```text
AI pipeline changes should always test empty AI response.
```

Save to:

```text
AI-Brain / Lessons-Learned
```

---

### Example 2

A project-specific file path is discovered:

```text
This project handles AI queue jobs in server/index.js.
```

Save to:

```text
repo/docs/project-map.md
```

---

### Example 3

A project-specific risk is discovered:

```text
The local AI fallback breaks if Ollama is unavailable.
```

Save to:

```text
repo/docs/risk-registry.md
```

Potential summary to AI-Brain:

```text
Local AI projects need explicit fallback tests.
```

---

## 7. Final rule

AI should not let important learning disappear inside a chat.

If knowledge can help future work, it should be proposed for saving.
