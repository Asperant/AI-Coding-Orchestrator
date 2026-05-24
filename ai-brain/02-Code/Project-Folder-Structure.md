# Project Folder Structure

Yeni bir yazılım projesi başlatırken kullanılacak temel klasör/dosya yapısı.

## Root files

```text
AGENTS.md
README.md
.env.example
.gitignore
```

## Docs

```text
docs/
  product-context.md
  architecture.md
  ai-coding-rules.md
  testing-checklist.md
  decisions/
  bug-fixes/
  lessons/
```

## GitHub

```text
.github/
  pull_request_template.md
```

## AI prompts

```text
prompts/
  feature-spec.md
  code-review.md
  debug.md
  diff-review.md
  safe-refactor.md
```

## Purpose

### AGENTS.md
Project-specific AI rules.

### docs/product-context.md
What the product is, who it serves, and what it should not do.

### docs/architecture.md
Tech stack, folder structure, data flow, and main technical decisions.

### docs/ai-coding-rules.md
Project-specific coding behavior for AI tools.

### docs/testing-checklist.md
Manual and automated test expectations.

### docs/decisions/
Technical and product decision records.

### docs/bug-fixes/
Important bug fixes and root causes.

### docs/lessons/
Reusable lessons learned while building the project.

### prompts/
Project-specific prompt templates.

### .github/pull_request_template.md
Quality gate before merging code.