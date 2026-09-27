# Evaluation rubric

Apply the rubric at question or multi-turn-chain level. Prefer categorical verdicts over impressionistic scoring.

## Deterministic gates

These checks are authoritative and run before model judgment:

- schema and required fields are valid;
- question IDs and chain IDs are unique;
- every evidence reference resolves;
- multi-turn numbers are contiguous from 1;
- a chain contains at least two turns;
- forbidden business-output fields are absent;
- target-brand spelling and brand-visibility labels match the wording;
- exact duplicate questions and variants are absent.

## Semantic dimensions

### Evidence grounding

`pass` only when the cited excerpt supports the question's scene, constraint, or expressed concern. Brand pages can support product facts but not user demand. Fail unsupported intent claims and citations used only because they mention the same product.

### Scene validity

The scene must represent a user, task, trigger or context, constraint, and decision stage to the degree supported by evidence. A keyword, product category, or demographic label alone is not a scene.

### Intent validity

The intent must explain the observed questions and actions without inventing undisclosed psychological or sensitive traits. Require more than one weak isolated signal for latent intent unless the user directly states it.

### Question quality

The question must sound like a plausible user request, test one identifiable decision need, and avoid forcing the target brand as the desired answer. Variants must preserve the same scene, intent, and decision stage while changing expression naturally.

### Multi-turn coherence

Later turns must depend on earlier context and progressively narrow, validate, compare, or operationalize the same underlying objective. A list of independent questions is not a multi-turn chain.

### Coverage and redundancy

Evaluate whether validated evidence-backed scenes and decision stages are represented. Do not maximize question count. Flag semantic duplicates and distinguish a legitimate wording variant from a separate test case.

### Content-brief validity

When content guidance is present, verify that the content job follows from the scene and intent, the must-answer items respond to observed user questions, and at least one usable non-brand evidence record supports demand. Check that `conditional_fit` names its conditions, `education_only` does not smuggle in a recommendation, and all proof requirements and claim boundaries are operational enough for a content generator to follow.

## Live GEO observation

For every AI-product run, record:

- exact product and visible model/version when available;
- single-turn or multi-turn state and preceding turns;
- exact response and cited sources;
- whether the target brand is absent, mentioned, compared, or recommended;
- whether statements about the target brand are accurate and supported;
- whether the response addresses the user's actual intent;
- run timestamp and repeat index for reproducibility.

Brand mention, recommendation, factual accuracy, citation quality, and intent satisfaction are separate measures. Never combine them into one unexplained score.

## Regression protocol

- Freeze a representative test set before comparing prompt or model versions.
- Include ordinary, ambiguous, sparse-evidence, multi-turn, adversarial, and brand-leakage cases.
- Randomize and blind pairwise semantic comparisons where practical.
- Keep run settings equal across versions.
- Add confirmed production failures to the regression set.
- Periodically compare automated judgments with human review and record disagreements.
