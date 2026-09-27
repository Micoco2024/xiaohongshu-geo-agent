---
name: xiaohongshu-geo-question-bank
description: Discover evidence-grounded Xiaohongshu user questions, scenes, and intents, then generate a GEO question bank or content-generation briefs. Use for brand insight, qualitative coding, intent inference, GEO question design, and insight-led content guidance. Do not use for unsupported generic copywriting, crawling, ranking reconstruction, or GEO answer scoring.
---

# Xiaohongshu Question Insight Agent

Use the short product name **小红书问题洞察 Agent**. Build one evidence-grounded insight core from scenes, question paths, and intents. Export either a GEO question bank, content-generation briefs, or both according to the user's request; never repeat discovery and analysis for each output.

## Entry input

Require only:

- target brand name.

Automatically discover the category, products, aliases, competitors, public Xiaohongshu evidence, scenes, and intents. Authorized merchant facts and customer-service questions are optional enrichments acquired through available tools or uploaded documents.

Do not ask whether the merchant has an API or customer-service data before starting. Begin public discovery immediately. When a relevant merchant or customer-service tool is available, call it directly; let the tool initiate its normal authorization flow. Never ask the merchant to paste credentials into chat.

If the brand name is materially ambiguous, ask only the minimum question needed to disambiguate it. If neither public Xiaohongshu material nor authorized customer-service material contains usable user expressions, do not manufacture scenes, intents, or questions; return the coverage limitation and missing evidence. Customer-service-only findings must not be presented as Xiaohongshu prevalence or platform behavior.

## Read supporting guidance

- Read [references/input-modes.md](references/input-modes.md) first to route public discovery, merchant facts, and customer-service questions with minimal human intervention.
- Read [references/brand-only-entry.md](references/brand-only-entry.md) when starting from a brand name and performing automatic discovery.
- Validate the normalized profile with [schemas/brand-profile.schema.json](schemas/brand-profile.schema.json) before starting evidence analysis.
- Register and validate sources with [schemas/evidence-record.schema.json](schemas/evidence-record.schema.json); use deterministic evidence IDs so repeated runs retain the same references.
- Read [references/research-method.md](references/research-method.md) when discovering scenes, coding content, reconstructing question paths, or inferring intent.
- Read [references/output-schema.md](references/output-schema.md) whenever generating, validating, or exporting the final question bank.
- Read [references/content-guidance.md](references/content-guidance.md) when insights will guide Xiaohongshu content generation.
- Validate the final machine-readable deliverable with [schemas/question-bank.schema.json](schemas/question-bank.schema.json) and semantic checks before delivery.
- Validate content briefs with [schemas/content-guidance.schema.json](schemas/content-guidance.schema.json).

## Workflow

1. Start from the brand name and immediately run public Xiaohongshu discovery.
2. Inspect the available tools. Directly invoke relevant merchant-data and customer-service connectors; the connector, not a preliminary chat question, handles authorization.
3. If a connector is unavailable, unsupported, or authorization is declined, continue without repeated prompts. Offer customer-service document upload as the fallback; if no document is supplied, continue with public evidence and report the coverage gap.
4. Normalize discovered or API-confirmed facts into the shared brand-profile structure. Keep customer-authored service questions in the user-question corpus rather than treating them as brand facts.
5. Register each usable source with a stable evidence ID. Preserve the public URL or authorized internal source identifier, context, and exact excerpt used.
6. Split Xiaohongshu titles, posts, comments and replies, plus authorized customer-service question turns, into meaning units. Code user tasks, triggers, contexts, constraints, decision stages, concerns, actions, and desired outcomes.
7. Build candidate scenes as combinations of user, task, trigger, context, constraint, and decision stage. A topic or keyword alone is not a scene.
8. Validate candidate scenes with brand-free category, need, pain-point, and usage-language evidence where available. Separate organic demand from official, commercial, duplicated, or templated content.
9. Map explicit questions to decision stages. Distinguish an observed same-user sequence from a cross-user inferred pathway; never present the latter as one person's actual journey.
10. Infer the underlying intent that best explains the questions and actions. Record alternative explanations and contradictory evidence before accepting the intent.
11. Build one validated scene-intent insight core. From it, generate GEO questions, content briefs, or both as requested.
12. Validate each requested output against its schema, remove unsupported or semantically duplicate items, and retain evidence references.

## Runtimes

There are two ways to run this agent. Both produce the same files in `../xiaohongshu-geo-workbench/data/`, so the web workbench can display either.

### A. Inside Claude Code or Codex (no API key)

Use this when the agent runs as a skill in Claude Code or Codex. The client does discovery and writing itself, reading Xiaohongshu through the user's own logged-in Chrome (Claude in Chrome for Claude Code, ChatGPT for Chrome for Codex); `tools/local_run.py` does normalization, evidence IDs, validation, the deterministic gates, and storage.

1. **Reuse before searching.** List `../xiaohongshu-geo-workbench/data/evidence/<brand>/`. If a snapshot exists, tell the user its date and evidence counts and reuse it unless they ask for a fresh search. Searching is the expensive step.
2. **Discover.** Search inside xiaohongshu.com in the user's Chrome, following `references/brand-only-entry.md`. Open each note before citing it. Set `verification` to `opened_page` only when the note was opened and the excerpt appears in it verbatim; otherwise use `search_result_only`. If the browser extension is not connected or the user is not logged in to Xiaohongshu, stop and tell the user which of the two to fix. If a page will not open, keep it as `search_result_only` and do not reconstruct its text from the snippet. Do not attempt to bypass login. Pace reading (a few seconds between notes) and stop when search or pages stop responding; that is rate limiting.
3. **Save evidence.** Write the result as JSON matching `schemas/brand-discovery.schema.json` to a scratch file, then run
   `python3 tools/local_run.py save-evidence --brand <brand> --raw <file>`.
   The output lists the usable evidence IDs; only these may be cited. If `status` is `insufficient` or `ambiguous`, stop and report the coverage note instead of generating questions.
4. **Generate.** Read `references/research-method.md` and `references/output-schema.md`, then write the question bank as JSON matching `schemas/question-bank.schema.json`, citing only the usable evidence IDs from step 3.
5. **Validate and save.** Run
   `python3 tools/local_run.py save-bank --snapshot <snapshot_id> --bank <file>`.
   If it reports an error or any failed check, fix the bank and run it again. Report the release decision and the path of the saved run.
6. **Live AI test (only when the user asks).** Run
   `python3 tools/local_run.py live-plan --run <run_id> --products 点点,豆包 --repeats 1`
   to list what to ask each product. Ask each question in a fresh conversation (for a chain, ask the turns in order in one conversation), capture the full answer and any cited sources verbatim, and save them with
   `python3 tools/local_run.py live-record --run <run_id> --records <file>`.
   Also open the answer's source list (for 点点, the "ai总结N篇笔记生成" chip) and record every cited note in `sources` with title, url, author, author_type, note_type, published date, likes/collects/comments as shown, and a short excerpt. The session file then reports what cited notes share, split by answers that named the brand and answers that did not, and how many cited notes are already in our evidence. Treat these as associations in a small sample, not causes.
   Brand mention is detected automatically; record `recommended` or `compared` only when the answer clearly does so, and leave accuracy and intent as `review` unless checked against the evidence. Pace browser use and stop if a product blocks or rate-limits the account. Live results are reported separately and never change the question-bank release decision.

### B. Claude API (web workbench)

With `ANTHROPIC_API_KEY` and the `anthropic` Python SDK, `tools/agent_runner.py` runs discovery (`tools/brand_discovery.py`) and generation (`tools/generation_agent.py`) through `tools/claude_client.py` with structured outputs, then the local semantic validator. It owns automatic discovery, the evidence sufficiency gate, optional merchant-fact enrichment, and final question-bank generation. Keep API credentials in the server environment; never place them in prompts, source files, or deliverables.

## Non-negotiable constraints

- Use Xiaohongshu merchant facts and Xiaohongshu content as evidence. An external search engine may discover a Xiaohongshu page but is not itself the content authority.
- Do not claim platform-wide coverage, true search volume, internal ranking, personalization logic, or algorithm weights.
- Do not treat merchant facts or brand marketing as proof of user demand.
- Do not infer intent directly from one isolated keyword or question when supporting context is absent.
- Mark the difference between directly observed content and analytical inference in internal records.
- Do not infer undisclosed sensitive traits or make clinical psychological judgments.
- Use only authorized APIs and publicly accessible data. Do not bypass login, verification, signatures, rate limits, or platform controls.
- Attempt normal tool authorization without a preliminary availability question. A declined or failed authorization is a routing result, not permission to retry repeatedly or bypass controls.
- Minimize human intervention: ask only for material brand disambiguation, an authorization decision presented by the tool, or a document upload when no connector can supply customer-service questions.
- Keep deterministic counts and deduplication outside model judgment when tools are available.
- Do not pre-decide that the target brand deserves recommendation. Questions must test discovery and representation, not encode the desired answer.

## Deliverables

By default, return the GEO question bank plus a short coverage note. When the user requests content guidance, also return evidence-grounded content briefs. Do not expose raw codebooks, evidence grades, confidence decimals, priority scores, or review dates as business deliverables unless requested.

The question bank must preserve:

- main question and natural-language variants;
- question type;
- single-turn or multi-turn mode;
- whether the brand is named in the question;
- linked scene and intent;
- decision stage;
- target brand;
- evidence references;
- chain ID and turn number for multi-turn questions.

Content guidance must preserve scene, intent, user questions, content job, must-answer items, user language, proof requirements, brand-entry conditions, claim boundaries, and evidence references. It guides later content generation; it is not the final post or publishing action.
