# Brand-name-only entry

The normal user input is one brand name. Category, products, competitors, scenes, intents, and questions are discovered downstream rather than requested upfront.

```text
brand name
→ brand disambiguation
→ Xiaohongshu public-page discovery
→ brand/profile normalization
→ evidence verification
→ qualitative analysis
→ GEO question bank
```

Merchant and customer-service access are optional. When relevant tools exist, invoke them directly and let the tools request authorization; do not ask the user to inventory available APIs before starting. Merchant data enriches brand or product facts. Customer-service connectors or uploaded documents add customer-authored questions and observed conversation paths.

## Discovery rules

- Expand the brand into alias, category, product, usage, pain-point, comparison, purchase, comment, and follow-up searches.
- Use search engines or hosted web search only to discover public Xiaohongshu pages.
- A directly opened Xiaohongshu page with a preserved excerpt may become usable evidence.
- A search-result title or snippet is only a candidate and cannot support a final question.
- Brand, merchant, shop, and product pages support brand facts; they do not prove user demand.
- If the name maps to materially different brands, return `ambiguous` and request one discriminating answer.
- If public access yields no usable user expression, attempt authorized customer-service input through an available connector or document upload. Return `insufficient` only when no usable user expression remains across those inputs.

The system does not bypass login, verification, signatures, rate limits, robots controls, or other platform safeguards. A declined authorization is accepted without repeated prompting. The system does not promise platform-wide completeness, and customer-service-only findings are not described as Xiaohongshu-wide patterns.
