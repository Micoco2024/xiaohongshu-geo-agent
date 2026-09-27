# Automatic input routing

The user normally supplies only a brand name. Start work immediately and acquire the strongest available inputs without asking the user to inventory APIs or documents first.

```text
brand name ─→ public Xiaohongshu discovery ───────────────────────┐
           ├→ merchant-data tool → authorization → brand facts ──┤
           └→ customer-service tool → authorization ─┐            ├→ shared analysis
                 customer-service document upload ───┴→ questions ┘
```

Merchant facts and customer-service questions have different roles. Do not merge them merely because both came from the merchant. Do not duplicate qualitative analysis, intent inference, or question-generation logic across acquisition paths.

## Routing order

1. Begin public Xiaohongshu discovery from the brand name.
2. Inspect available tools rather than asking whether an API exists.
3. Directly call a relevant merchant-data or customer-service connector. The connector presents its normal authorization screen when authorization is required.
4. If authorization succeeds, retrieve only the authorized fields and continue.
5. If authorization is declined, the connector is unavailable, or its scopes do not include the needed data, do not repeatedly ask or retry. Continue with the data already available.
6. For missing customer-service questions, expose a document-upload fallback. Accept only merchant-authorized materials and process them after removing unnecessary personal data.
7. If neither a customer-service connector nor a document is available, finish with public evidence and state the missing coverage; do not block the whole run.

The Agent must never ask for passwords, tokens, cookies, or secret keys in conversation. Authorization belongs in the connector's authorization flow.

## Shared normalized brand profile

Normalize known facts with [`../schemas/brand-profile.schema.json`](../schemas/brand-profile.schema.json). A minimal non-API example is available at [`../schemas/brand-profile.example.json`](../schemas/brand-profile.example.json).

Unknown nullable fields may remain `null`, and unknown collections may remain empty. Record material gaps in `missing_facts`; never infer missing facts merely to complete the schema.

This profile is an internal input object, not part of the final GEO question-bank deliverable.

## Merchant-data tool

Use this input automatically when a relevant tool is available. A missing or declined connection must not block brand-name-only startup.

### Purpose

Use the merchant API to establish reliable brand and product facts. It does not prove user demand, scene prevalence, or intent.

### Procedure

1. Read only the fields and resources authorized for the task.
2. Retrieve the brand, product, SKU, category, attribute, FAQ, and availability fields that the actual API exposes.
3. Map provider identifiers to the shared profile without leaking credentials or raw secrets into outputs.
4. Record the source identifier for each fact and leave unavailable fields empty.
5. Continue with the shared Xiaohongshu public-evidence workflow to discover scenes and intents.

### Stop conditions

- Stop on authorization failure, expired credentials, unavailable scopes, or platform verification requirements.
- Do not substitute private endpoints, reverse-engineered signatures, or unrelated account data.
- If the API is partially available, keep verified fields and mark the rest in `missing_facts`; do not downgrade silently to guessed values.

## Public-evidence fallback

Use this path concurrently with tool discovery and as the fallback when merchant access is unavailable.

### Source order

Build the initial brand profile from the strongest available sources in this order:

1. a user-supplied brand or product list;
2. publicly visible Xiaohongshu official-brand, shop, or product pages;
3. repeated product entities found in public Xiaohongshu posts, treated as candidates until corroborated.

Do not treat a single user post as an authoritative product fact.

### Procedure

1. Require at minimum the target brand name and category or product scope.
2. Extract candidate aliases, product names, categories, and attributes from public Xiaohongshu evidence.
3. Separate confirmed facts from candidates and ambiguous terms.
4. Ask for user confirmation only when ambiguity would materially change the evidence search or question bank.
5. Leave SKU IDs, full catalogs, attributes, or FAQs empty when they cannot be verified.
6. Continue through the same shared evidence, coding, scene, intent, and question-generation workflow used by API mode.

### Limits

- Do not claim a complete product catalog.
- Do not infer unavailable merchant IDs, inventory, sales, order, or operational data.
- Do not use external-platform content as proof of Xiaohongshu scenes or intent.

## Shared downstream workflow

After acquisition and normalization, all available inputs use the same analysis steps:

```text
register Xiaohongshu evidence
→ register authorized customer-service questions when available
→ retain merchant facts for claim verification
→ meaning-unit coding
→ candidate-scene construction
→ brand-free validation
→ question-path analysis
→ intent inference
→ GEO question-bank generation
→ schema validation
```

The final question-bank schema and evidence requirements must not vary by acquisition path. A short coverage note may state which sources were available and which user-question or brand-fact coverage was missing.

## Customer-service questions

Customer-service questions may arrive through either:

- an authorized customer-service API or connector; or
- merchant-uploaded chat exports, tickets, call summaries, FAQ source materials, or other customer-service documents.

Customer-authored turns may support question expressions, observed multi-turn paths, objections, usage problems, and after-sales intents. Agent-authored replies provide context or brand/service facts; they must not be counted as customer demand. Preserve a pseudonymous conversation reference and turn order when available. Do not combine different conversations into one observed user journey.
