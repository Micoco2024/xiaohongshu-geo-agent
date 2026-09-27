# Research method

Use this reference for scene discovery, qualitative coding, question-path construction, and intent inference.

## Method position

Use a grounded-theory-inspired abductive thematic analysis. Do not describe the work as full grounded theory unless the project actually performs theoretical sampling, constant comparison, memoing, negative-case analysis, researcher review, and an explicit saturation assessment.

The analysis chain is:

```text
source evidence
→ meaning units
→ first-order codes
→ second-order themes
→ scenes
→ explicit questions and decision stages
→ question paths
→ latent intents
→ GEO questions
```

## Units and definitions

### Meaning unit

The smallest excerpt that independently expresses a need, concern, experience, judgment, action, or expected result. Preserve its evidence ID and local context.

### Scene

A concrete situation combining as many of the following as the evidence supports:

```text
user + task + trigger + context + constraint + decision stage
```

Do not promote broad topics such as “sunscreen,” “travel,” or “mother and baby” to scenes.

### Question path

A sequence of questions serving one decision process, commonly moving through:

```text
need recognition
→ solution exploration
→ category choice
→ brand comparison
→ risk validation
→ purchase decision
→ usage optimization
→ after-sales resolution
```

Use `observed_session` internally only when same-user or same-thread evidence establishes sequence. Otherwise use `inferred_pathway` internally and never claim it represents a real individual's complete journey.

### Intent

The progress the user is trying to make. Express it through supported elements:

```text
trigger
+ desired progress
+ obstacle or uncertainty
+ decision criteria
+ risk to avoid
+ functional/emotional/social outcome
+ expected next action
```

One scene may contain multiple intents, and one intent may span related scenes.

## Coding procedure

1. Create first-order codes close to the user's language and phrased as needs or actions, such as “avoid discovering incompatibility only after purchase.” Avoid noun-only labels such as “price” or “sensitive skin.”
2. Compare codes across authors, dates, content types, and queries. Keep meaningful differences in user, task, trigger, constraint, or decision stage.
3. Group codes into themes describing conditions, actions, and expected outcomes.
4. Propose a scene only when multiple meaning units form a coherent situation.
5. Form an intent as the best explanation of the relevant questions and actions, then test at least one alternative explanation when the evidence permits.
6. Preserve contradictory or negative cases rather than forcing all evidence into the dominant interpretation.

## Brand-free validation

When data access allows it, remove the target brand from candidate-scene language and inspect category, need, pain-point, and usage content. Use this to distinguish:

- demand that exists independently of the brand;
- brand-established associations;
- unmet or weakly occupied opportunities;
- risk or misunderstanding patterns;
- marketing-created associations unsupported by organic discussion.

Brand-free validation is an analytical safeguard, not a requirement to reconstruct Xiaohongshu search ranking.

## Evidence handling

For each source retain internally:

- stable evidence ID;
- Xiaohongshu URL or authorized source identifier;
- source type;
- author identifier in minimized or hashed form when needed;
- publication/capture context when available;
- exact supporting excerpt;
- commercial, official, duplicated, templated, or uncertain-content marker.

Use search-result snippets as weaker context when the full Xiaohongshu page is unavailable. Do not treat snippets as complete representations of the source.

## Acceptance rules

Accept a scene-intent pair for question generation only when:

- the evidence supports a concrete scene rather than a topic label;
- the intent explains the linked questions or actions;
- the conclusion is not based solely on one promotional source;
- meaningful counterevidence has been considered;
- every generated question can cite at least one supporting evidence reference.

Evidence volume thresholds may vary by category. Do not fabricate universal cutoffs or numerical confidence scores.

## Question construction

Generate only user-plausible questions supported by the scene and intent. Cover relevant types without forcing a fixed ratio:

- need and problem recognition;
- how-to or strategy;
- category choice;
- brand discovery or recommendation;
- competitor comparison;
- brand verification;
- risk and objection;
- usage optimization;
- after-sales resolution.

Prefer brand-free questions when testing whether an AI system independently surfaces the target brand. Use named-brand questions for comparison, verification, risk, usage, and after-sales intents when supported by evidence.

Natural-language variants must preserve the same scene, intent, and decision stage while varying realistic phrasing. Do not create superficial synonym substitutions that add no testing value.
