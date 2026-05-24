# Prompt Quality Rubric

Purpose: evaluate prompt quality before relying on a prompt in repeated workflows.

## Scoring

Score each area from 1 to 5.

## 1. Role clarity

- Is the AI role explicit?
- Does the prompt define the perspective or job clearly?

## 2. Task clarity

- Is the task concrete?
- Is the expected scope obvious?

## 3. Constraints

- Are hard limits explicit?
- Are unsafe or out-of-scope actions blocked clearly?

## 4. Output format

- Does the prompt define what the answer should look like?
- Is the format easy to review and compare?

## 5. File editing safety

- Does it say whether files may be edited?
- Does it protect against unrelated changes?

## 6. Verification / test request

- Does it ask for review, testing, or validation where needed?

## 7. Context efficiency

- Does it avoid unnecessary reading?
- Does it point to the smallest useful set of inputs?

## 8. Examples / few-shot usage

- Does the prompt use examples only when they improve quality?
- Are examples relevant rather than noisy?

## Interpretation

- `34-40`: strong reusable prompt
- `26-33`: usable but should be tightened
- `18-25`: weak or incomplete
- `<18`: do not rely on this prompt repeatedly without revision
