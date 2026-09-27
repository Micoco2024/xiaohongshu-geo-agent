# Research method: grounded theory

Use this reference for coding, category building, scene and intent formation, and question construction.

## Method position

The agent uses constructivist grounded theory (Charmaz) with the Strauss–Corbin coding paradigm for axial coding. Data collection and analysis alternate: each batch of notes is coded before the next batch is chosen, and what to collect next is decided by gaps in the emerging categories (theoretical sampling), not by a fixed keyword list. Collection stops at theoretical saturation, not at a fixed note count.

Honesty rules:

- Call the result "grounded-theory coding of N notes and M comments collected in K batches". Do not claim platform-wide findings.
- An automated run has no second human coder. Say so in the coverage note; do not report inter-coder agreement.
- Keep the analysis traceable: every open code cites evidence IDs, every higher level lists the codes it is built from. `tools/grounded_coding.py` enforces this.

```text
batch of notes and comments
→ open (initial) coding, line by line
→ focused coding (the most frequent / most explanatory initial codes)
→ axial coding: categories with properties, dimensions and the paradigm
     conditions · context · actions/interactions · consequences
→ memos after every batch
→ theoretical sampling: the next queries target the thinnest part of a category
→ repeat until saturation
→ selective coding: one core category that ties the categories together
→ scenes (from conditions + context) and intents (from actions + consequences)
→ GEO questions
```

## 1. Open coding

Code each meaning unit (a sentence or clause in a note, comment or reply that expresses a need, action, judgment, worry or outcome).

- Write codes as actions or processes in the user's terms: “赶早八前找地方坐一会儿”, not “场景” or “学生”. Nouns alone are not codes.
- Use in-vivo codes (the user's exact words, in quotation marks, `in_vivo: true`) when the phrasing itself carries meaning, e.g. “续杯到底能不能续”.
- Code comments and replies as carefully as the note body. On mature brands the note body is often promotional while the comments hold the real questions.
- Mark promotional, official, templated or duplicated sources in the evidence record; code them, but they cannot on their own support a category.
- Record `batch` on every code.

## 2. Focused coding

After each batch, compare open codes across authors, dates and queries. Group those that express the same process under a focused code. Choose focused codes for analytic power, not frequency alone: a code seen twice that explains many others can outrank one seen ten times.

A focused code backed by one piece of evidence is provisional; the validator warns about it.

## 3. Axial coding: categories

A category is a phenomenon users deal with, e.g. “在固定预算里把会员权益用足”. For each category record:

- **Properties and dimensions**: what varies and between which ends, e.g. 规则清晰度：从完全不懂到熟练; 时间压力：从随意到赶时间. Properties are where later batches add detail; record `batch` on each.
- **Paradigm**, each part listing focused codes:
  - `conditions` — what triggers the phenomenon (causal conditions);
  - `context` — where, when, with whom, under which constraints;
  - `actions` — what users do or ask to handle it (strategies, interactions);
  - `consequences` — what they hope for or what happens (outcomes, including emotional and social).
- **Negative cases**: evidence that contradicts the category. Keep it; it sharpens properties and prevents forcing.

An empty paradigm part is the most important output of a batch: it is the next sampling target.

## 4. Memos

Write at least one memo per batch. A memo records a comparison, why codes were merged or split, a hunch about how categories relate, or a negative case and what it changes. Memos are how the analysis shows its reasoning; they cite code or category IDs in `about`.

## 5. Theoretical sampling and saturation

After coding a batch:

1. List the gaps: categories with empty paradigm parts, thin properties, provisional focused codes, negative cases not yet explained.
2. Turn each gap into one or two queries and add them to the collection plan with `purpose: "theoretical"` and the gap as `reason` (see `references/sampling.md`).
3. Collect the next batch from those queries first.

Saturation (computed by `saturation()` in `tools/grounded_coding.py`): the last two batches produced no new focused codes and no new category properties, with at least three batches collected. New open codes that fit existing focused codes do not break saturation. If collection is stopped by rate limits before saturation, say so; do not call the result saturated.

## 6. Selective coding: the core category

When categories are stable, name one core category that most categories relate to and that explains variation across them. It frames the question bank; it does not itself become a question.

## 7. From categories to scenes and intents

- **Scene** = one category, described through its conditions and context (who, when, where, trigger, constraint). In the question bank, `scene_id` is the `category_id` and `scene` is that description. `save-bank` rejects scene IDs that are not categories of the coding record.
- **Intent** = the progress users are trying to make in that category, taken from actions and consequences. Record at least one alternative explanation in a memo when the evidence allows.
- **Question paths** follow the decision stages visible in the actions. Only evidence from one thread (a note and its replies, one customer-service conversation) can show a real sequence; a path assembled across users is an inferred pathway and is labelled as such.

## Brand-free validation

Mature brands dominate their own search results with official and promotional content. Collect brand-free queries for the category's needs (see `references/sampling.md`) and code them in the same way. Use them to separate:

- demand that exists independently of the brand;
- associations the brand already holds;
- needs the brand has not entered;
- risks, complaints and misunderstandings;
- associations created only by marketing, without organic discussion.

## Evidence handling

For each source retain: stable evidence ID; Xiaohongshu URL or authorized source identifier; source type (post, comment, reply); author role; capture context; exact excerpt; promotional/official/templated marker where it applies. Search snippets are candidates only and cannot support a code.

## Acceptance rules

Accept a category for question generation only when:

- it is grounded in evidence from more than one author;
- it does not rest only on promotional or official sources;
- its paradigm has conditions or context (to form a scene) and actions or consequences (to form an intent);
- negative cases have been considered in a memo;
- every question built on it can cite supporting evidence.

Do not invent numeric thresholds or confidence scores.

## Question construction

Generate only user-plausible questions supported by a category's scene and intent. Cover relevant types without forcing a fixed ratio:

- need and problem recognition;
- how-to or strategy;
- category choice;
- brand discovery or recommendation;
- competitor comparison;
- brand verification;
- risk and objection;
- usage optimization;
- after-sales resolution.

Prefer brand-free questions when testing whether an AI system independently surfaces the target brand. Use named-brand questions for comparison, verification, risk, usage and after-sales intents when supported by evidence. Prefer the users' own wording from in-vivo codes.

Natural-language variants must keep the same scene, intent and decision stage while varying realistic phrasing.
