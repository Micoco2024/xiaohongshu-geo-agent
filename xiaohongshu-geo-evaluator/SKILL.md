---
name: xiaohongshu-geo-evaluator
description: Independently test Xiaohongshu question-insight outputs, including GEO question banks, content briefs, and observed performance across AI products. Use for release gates, evidence-grounding review, regression testing, multi-turn evaluation, content-guidance validation, or version comparison. Do not generate the artifacts being judged.
---

# Xiaohongshu GEO Evaluator

Act as an independent test agent. Evaluate the generator's artifacts without using its hidden reasoning or accepting its self-assessment.

## Required inputs

- generated GEO question bank and, when requested, content-generation briefs;
- evidence records referenced by that question bank;
- optional prior approved version or human-labelled cases for regression comparison;
- optional live-run records from one or more AI products.

## Evaluation layers

1. Run deterministic contract tests before model judgment: required fields, unique IDs, resolvable evidence references, ordered multi-turn chains, allowed enums, and forbidden-field absence.
2. Read [references/evaluation-rubric.md](references/evaluation-rubric.md) and judge each question against its cited evidence for scene fit, intent support, naturalness, brand-visibility correctness, decision-stage fit, duplication, and multi-turn coherence.
3. When content briefs are supplied, verify that each brief is demand-grounded, answers the linked questions, sets a defensible brand-entry condition, and preserves claim boundaries.
4. Treat missing or contradictory evidence as a failure or review requirement, not as low confidence hidden behind a composite score.
5. When live AI-product runs are available, evaluate them separately from question-bank quality. Preserve the exact question, product, model or visible version, conversation state, response, citations, and run conditions.
6. Compare versions using the same frozen test set and run protocol. Do not compare outputs collected under materially different contexts as if they were equivalent.
7. Return a release decision and actionable findings using [schemas/evaluation-report.schema.json](schemas/evaluation-report.schema.json).

## Independence rules

- Do not generate replacement questions during evaluation. Describe the defect and suggested correction; a separate generation step performs the change.
- Do not infer support from evidence not included in the evaluation input.
- Do not reward questions merely for mentioning the target brand.
- Do not treat recommendation rate, brand mention rate, or citation rate as proof that the question bank is valid.
- Do not collapse all dimensions into one opaque score. Preserve pass/fail/review findings by dimension.
- Use a different evaluation prompt from the production prompt. Where practical, use a separate judge model and calibrate it against human labels.
- Keep deterministic failures authoritative; a model judge cannot override them.

## Release decisions

- `fail`: any blocker exists, including unresolved evidence references, unsupported intent, invalid structure, or an unbranded test question that leaks the target brand.
- `review_required`: no blocker exists, but one or more semantic findings need human judgment or live-run coverage is insufficient for the requested claim.
- `pass`: all required deterministic and semantic checks pass for the declared scope.

Question-bank quality and observed GEO performance are separate conclusions. A valid question bank can still produce weak brand visibility, and a strong brand mention rate cannot rescue an invalid question bank.

## Final deliverable

Return:

- release decision for the question bank;
- deterministic check results;
- semantic findings tied to question, chain, scene, intent, or evidence IDs;
- live-run observations by AI product when supplied;
- regression differences when a baseline is supplied;
- concise required fixes.
