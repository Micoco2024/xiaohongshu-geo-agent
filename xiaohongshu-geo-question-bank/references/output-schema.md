# GEO question bank output schema

Use this schema for the final business deliverable.

The canonical machine-readable contract is [`../schemas/question-bank.schema.json`](../schemas/question-bank.schema.json). The examples below explain its records in human-readable form.

## Single-turn record

```json
{
  "question_id": "GEO-Q-0001",
  "question": "敏感肌通勤用什么防晒？",
  "question_variants": [
    "敏感肌每天上班适合什么防晒？",
    "有没有适合敏感肌日常通勤的防晒？"
  ],
  "question_type": "brand_recommendation",
  "test_mode": "single_turn",
  "brand_visibility": "unbranded",
  "scene_id": "XHS-SCN-001",
  "scene": "敏感肌上班族夏季通勤防晒",
  "intent_id": "XHS-INT-001",
  "intent": "降低日常防晒的购买和使用试错风险",
  "decision_stage": "solution_exploration",
  "target_brand": "品牌A",
  "evidence_refs": ["EV-001", "EV-002"]
}
```

## Multi-turn record

```json
{
  "question_chain_id": "GEO-CHAIN-001",
  "test_mode": "multi_turn",
  "scene_id": "XHS-SCN-001",
  "scene": "敏感肌上班族夏季通勤防晒",
  "intent_id": "XHS-INT-001",
  "intent": "降低日常防晒的购买和使用试错风险",
  "target_brand": "品牌A",
  "turns": [
    {
      "question_id": "GEO-Q-0101",
      "turn": 1,
      "question": "敏感肌上班通勤用什么防晒比较合适？",
      "question_variants": [],
      "question_type": "brand_recommendation",
      "brand_visibility": "unbranded",
      "decision_stage": "solution_exploration",
      "evidence_refs": ["EV-001"]
    },
    {
      "question_id": "GEO-Q-0102",
      "turn": 2,
      "question": "我还要化妆，哪些不容易和粉底打架？",
      "question_variants": [],
      "question_type": "risk_validation",
      "brand_visibility": "context_dependent",
      "decision_stage": "criteria_narrowing",
      "evidence_refs": ["EV-002"]
    }
  ]
}
```

## Required values

### `question_type`

Use the closest supported value:

- `need_recognition`
- `how_to`
- `category_choice`
- `brand_recommendation`
- `competitor_comparison`
- `brand_validation`
- `risk_validation`
- `usage_optimization`
- `after_sales`
- `purchase_decision`

Add a new value only when existing values materially misrepresent the question.

### `test_mode`

- `single_turn`
- `multi_turn`

### `brand_visibility`

- `unbranded`: the question does not name the target brand;
- `branded`: the question names the target brand;
- `context_dependent`: the current turn relies on a brand introduced earlier in the chain.

### `decision_stage`

Use a concise machine-readable stage, normally one of:

- `need_recognition`
- `solution_exploration`
- `category_choice`
- `criteria_narrowing`
- `brand_comparison`
- `risk_validation`
- `purchase_decision`
- `usage_optimization`
- `after_sales`

## Validation

Before delivery, verify:

- every record has a unique question ID;
- every multi-turn chain has a unique chain ID and ordered turns;
- each variant preserves the parent question's scene, intent, and decision stage;
- every question or turn has at least one evidence reference;
- `brand_visibility` matches the actual wording and prior turns;
- no question presupposes that the target brand must be recommended;
- semantically duplicate questions are removed unless wording variation is intentionally retained for testing.

## Excluded final fields

Do not include these in the final business deliverable unless the user explicitly requests them:

- target-brand role or eligibility judgments;
- scene type;
- priority labels or scores;
- evidence grades;
- confidence decimals;
- generation or review dates;
- expected recommendation outcome.
