# Project Onboarding Prompt

You are a senior software engineer onboarding into a new codebase. Use this prompt when introducing an AI tool to a new or existing project.

## Prompt

```text
Read my global instructions first.

I want to onboard this repository into my AI engineering system.

Before editing any files:
1. Inspect the repository structure.
2. Identify the project type, tech stack, and main folders.
3. Check whether AI-ready files already exist:
   - AGENTS.md
   - docs/product-context.md
   - docs/architecture.md
   - docs/ai-coding-rules.md
   - docs/testing-checklist.md
   - prompts/
   - .github/pull_request_template.md
4. Tell me what is missing.
5. Propose the smallest safe onboarding plan.

Rules:
- Do not edit files yet.
- Do not overwrite existing files.
- Do not create large documentation.
- Keep the onboarding minimal and useful.

After your inspection, answer with:
1. Project summary
2. Existing AI-ready files
3. Missing AI-ready files
4. Recommended next step
5. Files you would create if approved
```