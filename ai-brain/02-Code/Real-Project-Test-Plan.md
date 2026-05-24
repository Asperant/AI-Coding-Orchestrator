# Real Project Test Plan

Purpose: define how to test this AI-Brain on a real coding project.

## Test 1: project onboarding

**Goal:** Verify that the AI-Brain can onboard a real repository into the system with minimal drift.

**Prompt to use:** [[Project-Onboarding-Prompt]]

**Expected output:**
- project summary
- existing AI-ready files
- missing AI-ready files
- smallest safe onboarding plan

**Pass/fail criteria:**
- Pass if the AI inspects the real repo structure before recommending docs
- Pass if recommendations stay minimal and repo-specific
- Fail if the AI invents stack details or proposes large boilerplate docs

## Test 2: orchestrated coding task

**Goal:** Verify that the practical orchestrator prompt leads to small, scoped implementation behavior.

**Prompt to use:** [[Run-Orchestrated-Coding-Task]]

**Expected output:**
- task classification
- small plan
- limited file scope
- risk notes
- tests

**Pass/fail criteria:**
- Pass if the AI plans before coding and keeps changes small
- Pass if risk areas are identified before edits
- Fail if the AI jumps into large rewrites or ignores task type

## Test 3: multi-agent diff review

**Goal:** Verify that diff review becomes more practical, prioritized, and consolidated.

**Prompt to use:** [[Run-Multi-Agent-Diff-Review]]

**Expected output:**
- clear summary
- decision
- blockers or required fixes
- test suggestions
- memory/docs update suggestion

**Pass/fail criteria:**
- Pass if findings are severity-ordered and consolidated
- Pass if the review avoids noisy multi-agent dumping
- Fail if the review is generic or misses obvious risk areas

## Test 4: bug fix workflow

**Goal:** Verify that bug fixing follows expected/actual/root-cause/fix discipline.

**Prompt to use:** [[Debug-Prompt]]

**Expected output:**
- expected behavior
- actual behavior
- likely root cause
- minimal fix
- regression checks

**Pass/fail criteria:**
- Pass if the AI separates symptom from root cause
- Pass if the fix is minimal and testable
- Fail if the AI guesses blindly or proposes broad refactors

## Test 5: memory sync after task

**Goal:** Verify that reusable knowledge is saved to the right place after real work.

**Prompt to use:** [[Project-Memory-Sync-Rules]]

**Expected output:**
- decision about AI-Brain vs project docs vs both
- specific recommendation for what should be saved
- rationale tied to reusability

**Pass/fail criteria:**
- Pass if cross-project knowledge is routed to AI-Brain
- Pass if repository-specific details are routed to project docs
- Fail if the AI mixes project context into global memory without reason
