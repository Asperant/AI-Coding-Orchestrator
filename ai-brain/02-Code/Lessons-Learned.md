# Lessons Learned

Reusable lessons from coding, product development, and AI-assisted engineering. Each lesson should be cross-project applicable.

## Format

Each lesson follows this structure:

### YYYY-MM-DD — Short title

**Context:** What was I working on?

**Lesson:** What did I learn?

**Use later:** Where will I apply this?

---

## Lessons

### 2026-05-16 — AI coding systems need a compact entrypoint

**Context:** Building the AI-Brain vault. Initially the system had 40+ files with no clear entry point. Every AI tool had to figure out which files mattered, wasting context window tokens and producing inconsistent behavior.

**Lesson:** Any AI knowledge system needs a single compact file (~2-3KB) that contains the essential rules, identity, and workflow. Everything else is an expansion of that file. Without a clear entrypoint, AI tools either read too much (wasting tokens) or too little (missing critical rules).

**Use later:** Every future knowledge system or project documentation structure should start with one compact rules file. See [[CORE-RULES]].

---

### 2026-05-16 — Project-specific context belongs in project docs, not the global AI-Brain

**Context:** Early AI-Brain design mixed global engineering rules with project-specific product details (e.g., [Example Project] product context, specific tech stack details). This caused confusion about what was reusable and what was project-locked.

**Lesson:** Global AI-Brain should only contain cross-project engineering knowledge: workflows, prompts, templates, checklists, and reusable principles. Project-specific product context, architecture, file maps, risks, and test scenarios belong in each project's `docs/` folder. Mixing them creates stale data and scope confusion.

**Use later:** When starting any new project, create project docs inside the repo. Only save cross-project lessons and principles back to AI-Brain. See [[Project-Memory-Sync-Rules]].

---

### 2026-05-16 — AI tools work better with filled examples, not just empty templates

**Context:** The AI-Brain had many well-structured templates (Decision, Bug Fix, Project Map, Multi-Agent Review) but all were empty. AI tools reading them understood the structure but had no reference for expected quality, depth, or tone.

**Lesson:** Empty templates teach format but not quality. AI tools produce significantly better output when they can see a realistic filled example alongside the template. One good example is worth more than a page of format instructions.

**Use later:** Every new template should ship with at least one filled example in `07-Examples/`. See [[Example-Decision]], [[Example-Bug-Fix]], [[Example-Lesson]].

---

### 2026-05-17 — Multi-agent systems should start as role-switching prompts before becoming automated runtimes

**Context:** Designed an 8-agent + orchestrator architecture (Planner, Coder, Reviewer, Security, Tester, Architect, Product, Release). The design was architecturally sound but no current AI tool could execute it as a real multi-agent runtime.

**Lesson:** Multi-agent designs are valuable as mental models and review lenses, but building automated runtimes before the tooling supports it wastes effort. Start by using agent definitions as role-switching prompts within a single AI session. Graduate to automated orchestration only when MCP or similar tooling makes it practical.

**Use later:** Use [[Run-Orchestrated-Coding-Task]] and [[Run-Multi-Agent-Diff-Review]] as practical single-model orchestrator prompts. Keep agent definitions in `05-Agents/` as reference.

---

### 2026-05-17 — Every coding task must classify task type before implementation

**Context:** When AI tools were given coding tasks without explicit type classification, they treated everything as a generic feature. This caused them to miss security risks on auth changes, skip migration concerns on database changes, and ignore fallback testing on AI pipeline changes.

**Lesson:** Task type classification is the single most effective way to change AI behavior. Different task types (feature, bug fix, refactor, database change, security change, AI pipeline change) have fundamentally different risk profiles and require different review checklists. Classification must happen before any code is written.

**Use later:** Start every coding task with [[Task-Type-Rules]]. The priority order (Security > Database > AI Pipeline > Auth > Bug Fix > Feature > Refactor > UI > Test > Docs) should be enforced automatically through prompts.

---

### 2026-05-17 — AI pipeline changes must include fallback, timeout, malformed response, and regression tests

**Context:** An AI-dependent result generation feature broke in production when the AI service returned an empty response `{}`. The app showed an infinite loading spinner. The bug was missed because testing only covered the happy path.

**Lesson:** Any change to an AI pipeline — prompt changes, model changes, endpoint changes, queue changes — must be tested against at least 6 scenarios: service unavailable, empty response, malformed response, timeout, error response, and rapid repeated requests. If any scenario is untested, the change is not complete.

**Use later:** Add these 6 scenarios to every project's `docs/test-scenarios.md`. Reference this lesson in [[Pre-Flight-Checklist]] for AI pipeline tasks. See [[Example-Lesson]] for the detailed version.

---

### 2026-05-17 — Strong AI systems need fewer active entrypoints and clearer priority tiers

**Context:** As the AI-Brain grew, it gained more useful files, prompts, examples, and layers. The content quality improved, but onboarding risk increased because too many files looked like valid starting points.

**Lesson:** An AI system becomes more practical when it has a very small number of active entrypoints and a clear priority order for everything else. Good documentation is not enough; AI tools need a reliable activation path. Fewer front doors and stronger priority tiers reduce confusion, token waste, and inconsistent behavior.

**Use later:** Keep [[CORE-RULES]] as the compact first read. Use `README-FOR-AI.md` as onboarding and `Home.md` as navigation. Treat new documents as supporting layers unless they clearly need to become first-class entrypoints.

---

### 2026-05-17 — Multi-agent architecture should stay as role lenses until there is a real runtime

**Context:** The AI-Brain now has a mature V4 multi-agent architecture plus practical orchestrator prompts. The architecture is useful, but current day-to-day work still happens through a single active model rather than a true runtime agent system.

**Lesson:** Until there is a real runtime with controlled delegation, agent roles should be used as review lenses rather than treated as literal execution agents. This keeps the benefits of multi-perspective thinking without pretending that orchestration exists where it does not.

**Use later:** Use [[Run-Orchestrated-Coding-Task]] and [[Run-Multi-Agent-Diff-Review]] for practical work. Keep `05-Agents/` as the conceptual architecture and evaluation layer.

---

### 2026-05-17 — A global AI-Brain becomes more valuable when tested repeatedly on real repositories and diffs

**Context:** The AI-Brain improved most when it was exercised against a real repository, real onboarding work, real diff reviews, and repeated workflow tests instead of being designed only in theory.

**Lesson:** A global AI system gains value from contact with real work. Testing it on actual repositories, diffs, bug fixes, and documentation tasks reveals which rules are useful, which prompts are too abstract, and where the system needs fewer steps or better defaults.

**Use later:** Re-test the AI-Brain regularly using [[Real-Project-Test-Plan]], real onboarding tasks, and real diff reviews. Promote only the rules and prompts that survive real project pressure.

---

### 2026-05-17 — First real project onboarding test confirmed the AI-Brain workflow works

**Context:** Ran the first real project onboarding test against a live repository using Codex and the AI-Brain workflow. The task required repository inspection before editing, minimal onboarding docs creation, and a review pass on the created files without unnecessary rewrites.

**Lesson:** The AI-Brain onboarding workflow works in practice when the AI is guided to inspect first, keep scope small, and save project-specific context into repo docs. In this test, Codex successfully inspected a real repository before editing, identified the tech stack and main folders, created minimal AI-ready files (`AGENTS.md`, `docs/product-context.md`, `docs/architecture.md`, `docs/project-map.md`), and then reviewed those files without editing. The strongest improvement from the test was adding task-based inspect order to `project-map.md`. Project maps are much more useful when they include task-based inspect order, not only folder descriptions.

**Use later:** For future project onboarding, keep the first pass minimal and make sure every `docs/project-map.md` includes task-based inspect order for common task types. See [[Real-Project-Test-Plan]], [[Project-Map-Template]], and [[Decision-002-Project-Map-Must-Include-Task-Based-Inspect-Order]].
