# Global Project Starter Pack

Yeni bir yazılım projesi başlatırken bu starter pack kullanılır.

Amaç:
- Projeye AI ile çalışmaya hazır bir yapı eklemek
- Codex’in proje bağlamını anlamasını sağlamak
- Kod review, test, karar ve bug kayıtlarını standartlaştırmak

## Files to create

```text
AGENTS.md
docs/product-context.md
docs/architecture.md
docs/ai-coding-rules.md
docs/testing-checklist.md
docs/decisions/
docs/bug-fixes/
docs/lessons/
prompts/feature-spec.md
prompts/code-review.md
prompts/debug.md
prompts/diff-review.md
prompts/safe-refactor.md
.github/pull_request_template.md
```

## Codex prompt

Use this prompt inside a new project:

```text
Read my global instructions and my AI-Brain notes if needed.

Create an AI-ready project starter structure for this repository.

Use this structure:

AGENTS.md
docs/product-context.md
docs/architecture.md
docs/ai-coding-rules.md
docs/testing-checklist.md
docs/decisions/
docs/bug-fixes/
docs/lessons/
prompts/feature-spec.md
prompts/code-review.md
prompts/debug.md
prompts/diff-review.md
prompts/safe-refactor.md
.github/pull_request_template.md

Before editing:
1. Inspect the repository.
2. Tell me what type of project this appears to be.
3. Tell me which starter files you will create.
4. Do not overwrite existing files without asking.

After creating files:
1. List created files.
2. Explain how I should use them.
3. Suggest the first project-specific edits.
```

## Rule

This starter pack should be adapted per project.  
It should not blindly overwrite existing project documentation.