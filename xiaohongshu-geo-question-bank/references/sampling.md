# Sampling and paced collection

Read this before collecting evidence, and again before every batch.

## Why mature brands need a different approach

For a large brand (e.g. 星巴克) a plain brand-name search returns mostly official accounts, campaigns, new-product posts and paid content. Organic user voices are a small share of those results, and Xiaohongshu search slows down or stops after a burst of activity. Every page load has to count.

## Collection path

Use a low-impact, index-first path. The goal is to reduce repeated Xiaohongshu
search requests, not to evade access controls.

1. Run `collect-status` before touching the browser. If `collection_allowed` is
   false, stop until `resume_after`. Do not use a page load as a health probe.
2. Discover candidate Xiaohongshu URLs with one focused public-index query such
   as `site:xiaohongshu.com/explore 星巴克 第一次 怎么点`. A search engine may
   locate a Xiaohongshu page, but its title and snippet are never evidence.
3. Open at most four candidate Xiaohongshu notes directly and sequentially.
   Verify the exact note text, then read comments and expand useful replies on
   the same page. This makes each Xiaohongshu page load carry more evidence.
4. Use Xiaohongshu's own search only when public indexing does not produce
   usable candidates and the collection status allows a batch. Submit one
   planned query, inspect the result once, and do not reload or try URL variants.
5. Save and code the batch before planning another. A new batch starts only
   after the cooldown reported by `collect-status`.

Never rotate accounts, alter fingerprints, bypass verification, or retry a
blank/stale result page. A verification prompt is a hard stop for the user to
resolve, not a collection path.

## Where user voices are

In order of user voices per page load:

1. **Comment sections of notes with many comments.** One opened note can hold 20+ distinct users asking and answering. Scroll the comment area and expand replies before reading. Prefer notes whose comment count is high relative to likes (discussion, not just applause).
2. **Question-style notes** (“求问…”, “有没有人知道…”, “…值得吗”, “…踩雷”) — the body itself is a user question, and replies show real follow-ups (an observed sequence, usable for question paths).
3. **Experience and complaint notes** from ordinary accounts (few followers, no brand tag, no “合作” marker).
4. Official and campaign notes: use only for brand facts, and read their comments rather than their bodies.

## Query design

Build queries from four sources, recorded in the collection plan with a `purpose`:

| purpose | Pattern | Example (星巴克) |
|---|---|---|
| `seed` | brand + situation or need word | 星巴克 自习 · 星巴克 带娃 · 星巴克 早餐 · 星巴克 会员 |
| `seed` | brand + question or problem word | 星巴克 怎么点 · 星巴克 踩雷 · 星巴克 值得吗 · 星巴克 隐藏菜单 |
| `brand_free` | the need without the brand | 办公 咖啡店 安静 · 低因 咖啡 推荐 · 咖啡 会员 省钱 |
| `comparison` | brand vs alternatives users name | 星巴克 瑞幸 区别 · 星巴克 和 manner |
| `theoretical` | the gap in a category, after coding | (see research-method.md §5) |

Start with 4–6 seed queries spread over different situations, plus 1–2 brand-free and 1 comparison query. Do not start with the bare brand name.

Sort by 最新 as well as 综合 when the filter is available: the default order favours high-engagement promoted content, recent posts carry more ordinary users.

## Pacing and batches

- One normal batch = at most `pages_per_batch` page loads (currently 5; see
  `collect-status`), counting discovery result pages and opened Xiaohongshu
  notes. A recovery batch after a rate limit or an over-budget batch is capped
  at 3 pages.
- Report the pages actually loaded, even when over budget. The batch is still
  saved, flagged `over_budget`, and the next cooldown is the long one. Never
  under-report pages to fit the budget.
- Wait at least 10 seconds between Xiaohongshu page loads. Do not open notes in
  parallel. Reading and expanding comments on the current page does not consume
  another page load.
- After a normal batch, wait at least 20 minutes. After a rate limit or an
  over-budget batch, wait at least 90 minutes. `collect-status` is authoritative for `resume_after`.
- Skip notes already in `seen_note_ids` from `collect-status`.
- Code the batch before collecting the next one. Coding is also the natural pause for the site.
- Signs of rate limiting: search submits but the result list does not change,
  notes open blank or stop loading, the page falls back to the home feed, or a
  verification prompt appears. On any of these, stop immediately and save with
  `--queries-limited "<query>" --rate-limited`. The query remains planned for a
  later batch instead of being marked done.

## Per-batch commands

```bash
python3 tools/local_run.py collect-status --brand <brand>        # next batch number, planned queries, notes already read
python3 tools/local_run.py collect-plan --brand <brand> --queries <queries.json>
# … read up to pages_per_batch pages, write the batch as brand-discovery JSON …
python3 tools/local_run.py save-evidence --brand <brand> --raw <batch.json> --batch <n> \
        --pages <pages opened> --queries-done "<queries with usable result pages>"
# If a query was blocked before results loaded:
python3 tools/local_run.py save-evidence --brand <brand> --raw <batch.json> --batch <n> \
        --pages <pages opened> --queries-limited "<blocked query>" --rate-limited
python3 tools/local_run.py save-coding --brand <brand> --coding <coding.json>
```

Each batch's evidence is merged into one working snapshot (same snapshot id, duplicates dropped). The coding record covers all batches so far; `save-coding` reports uncoded evidence, validator warnings (the gaps) and saturation.

## When to stop

Stop collecting when any of these holds, and state which in the coverage note:

- `save-coding` reports saturation;
- the user's time or page budget is used up;
- the site keeps rate-limiting and the user chooses to stop.

Only the first may be described as saturated. With the others, generate questions only from categories that meet the acceptance rules and list the unsaturated categories as gaps.
