# Content guidance

Use the same validated evidence, scenes, question paths, and intents that feed the GEO question bank. Do not create a separate discovery or qualitative-analysis pipeline for content work.

```text
evidence
→ scene and intent insight core
   ├─→ GEO question-bank exporter
   └─→ Xiaohongshu content-brief exporter
```

Generate content guidance only when requested. The default GEO deliverable remains the question bank.

## Purpose

A content brief translates a validated scene-intent pair into a job for content. It does not generate the final title, body copy, image, video, publishing calendar, or platform action.

Each brief should explain:

- what situation the user is in;
- what explicit questions or linked questions reveal the need;
- what progress the content should help the user make;
- what the content must answer;
- which user-language expressions are worth preserving;
- what evidence or demonstration is required;
- whether and under what conditions the target brand can enter naturally;
- which unsupported claims or overgeneralizations must be avoided.

## Brand-entry rules

- `direct_fit`: available evidence supports the brand or product as a direct response to the stated need.
- `conditional_fit`: the brand is relevant only under named user conditions, constraints, or tradeoffs.
- `education_only`: the validated need supports educational content, but current evidence does not justify positioning the target brand as the answer.
- `not_supported`: evidence does not support brand-led content for this scene.

Do not convert every observed need into a brand recommendation. A useful content opportunity may be educational, comparative, risk-clarifying, or explicitly unsuitable for brand insertion.

## Evidence rules

- Every content brief must reference usable Xiaohongshu evidence.
- At least one referenced record must contain user, creator, or otherwise non-brand demand evidence supporting the scene or intent.
- Merchant API and official brand content may support product facts, proof requirements, or claim boundaries, but cannot establish user demand alone.
- Preserve contradictions and negative evidence as required caveats rather than deleting them to make the brief more favorable.

Validate the final brief collection with [`../schemas/content-guidance.schema.json`](../schemas/content-guidance.schema.json).
