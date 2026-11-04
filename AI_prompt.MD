# Support Accelerator AI — AI layer handoff

Paste everything below the line into Claude on the office laptop.

---

## YOUR ROLE

I am continuing development of the AI layer of a Django application called **Support Accelerator AI**. The AI layer is built and working. I need you to help me fine-tune retrieval quality from here.

Read this whole document before responding. It describes what exists and why. Do not propose rebuilding any of it, and do not ask me clarifying questions about the architecture — it is all stated below. If you need to see a specific file, ask for that file by name.

My working rhythm: explain what the next step does and why you planned it that way, then let me ask doubts, then give me the code. One step at a time.

---

## WHAT THE AI LAYER DOES

A Tier-1 support analyst types an issue in plain language. The assistant answers from our own knowledge base — not from the model's general knowledge — and shows which article it answered from plus any linked past Salesforce cases. Answers that have no knowledge base backing are labelled as general guidance.

The point is **groundedness**. The model must say what our runbooks say, even when that contradicts what a model would normally advise. Our proof case: asked about a client user who cannot sign in, an ungrounded model says "try resetting the password." Our knowledge base says the account is healthy and the user opened the wrong URL, so the grounded answer says **do not reset the password**. That reversal is how we verify grounding is actually working.

---

## ARCHITECTURE — THREE DISTINCT COMPONENTS

People conflate these. Keep them separate.

| Component | What it is | Where it runs | What it decides |
|---|---|---|---|
| **Embedding model** | Chroma's default, `all-MiniLM-L6-v2` | Locally, on my machine | Which chunks match the question |
| **LLM** | `gpt-4.1-mini_2025_04_14` via Azure OpenAI | Company UAIS gateway | How the answer is worded |
| **Regex** | Section splitting, alias expansion, PHI detection | Locally | Structure only — never what matches |

The LLM never chooses which articles are relevant. Retrieval does that, and the citations shown to the user are derived mechanically from retrieval metadata. This is deliberate: a model that picks its own citations can invent an article code, and a hallucinated citation is worse than none because it looks authoritative and the analyst will click it.

---

## FILE 1 — `chatbot/services/uais_client.py` (transport)

The only module that talks to the LLM gateway.

- `openai.AzureOpenAI` with `azure_ad_token_provider=get_token` — a callable the SDK invokes per request
- OAuth2 client credentials flow; token cached module-level behind a `threading.Lock`, refreshed with a 60-second safety margin before expiry
- **Synchronous.** An earlier version used `asyncio.run()` per call; that was removed because Django's request path is sync and wrapping it added failure modes without benefit
- `timeout=30` (from `UAIS_TIMEOUT`), `max_retries=2`, `default_headers={'projectId': PROJECT_ID}`
- JSON mode via `response_format={"type": "json_object"}`. **The word "json" must appear literally in the prompt** or the gateway rejects the request
- If the gateway rejects `temperature`, the call is retried without it
- Raises `UAISError` on failure; the caller degrades gracefully rather than crashing

**Hard rule: this module never logs prompt or response content.** It logs status, latency and token counts only. That is a PHI containment requirement, not a style preference.

Config comes from `.env`: `UAIS_ENABLED`, `UAIS_AUTH_URL`, `UAIS_SCOPE`, `UAIS_GRANT_TYPE`, `UAIS_CLIENT_ID`, `UAIS_CLIENT_SECRET`, `UAIS_ENDPOINT`, `UAIS_API_VERSION` (`2025-01-01-preview`), `UAIS_DEPLOYMENT`, `UAIS_PROJECT_ID`, `UAIS_TIMEOUT`.

---

## FILE 2 — `chatbot/services/kb_index.py` (retrieval)

ChromaDB `PersistentClient`, collection `knowledge_base`, configured with `hnsw:space: cosine`.

### Chunking

Articles are split into sections, not indexed whole. `SECTION_RE` matches a line that is either:

- a line ending in a colon, e.g. `Prerequisites:`, `Symptom:`, `Resolution:`
- a line starting `Step N`, e.g. `Step 3: Check if the user already exists`

If no headings are found, `_paragraph_chunks()` is the fallback and labels every section with the literal string `Section`.

**`Section` appearing in a retrieval log is a diagnostic, not a label.** It means that article has no detected headings and was chunked by paragraph. Paragraph chunks are long and diffuse, so they score measurably worse than focused section chunks and rank below well-formatted articles even when they are the correct answer. This has already bitten us once (see OPEN ITEM 1).

### Context headers

Before embedding, each chunk gets a header prepended:

```
Product: Optum Charge Capture (OCC, Charge Capture)
Category: User Management
Article: OCC-UM-001 - Charge OCC - External user creation
Section: Prerequisites
```

Two reasons. It makes each chunk self-describing, so a chunk retrieved in isolation still carries its product and article identity. And it solves alias matching — a question mentioning "Charge Capture" matches a chunk whose header contains the alias.

**Known cost of this design:** every chunk of the same product shares an identical first line, which pulls all of one product's chunks toward each other in vector space. This compresses the distance spread between articles of the same product. It is a real trade-off we accepted for self-describing chunks.

### Query expansion

`expand_query()` appends the full product name when it detects an alias in the question using word-boundary regex. So "OCC" becomes "OCC Optum Charge Capture" before embedding.

### Grounding and filtering

```python
def is_grounded(results):
    # Looks at the BEST hit only.
    return bool(results) and results[0]['distance'] <= GROUNDING_THRESHOLD


def filter_results(results):
    # Two caps, both needed.
    best = results[0]['distance']
    cutoff = min(GROUNDING_THRESHOLD, best + CITATION_MARGIN)
    return [r for r in results if r['distance'] <= cutoff]
```

The relative cap matters more than the absolute one. A query's best distance varies enormously with phrasing length — a full sentence scores around 0.24, a single acronym around 0.58. So "is this hit good in absolute terms" is the wrong question; "is this hit close to the best one" is the right one. A chunk at 0.55 sitting next to a best of 0.35 is not a co-source, it is a different topic sharing vocabulary.

`filter_results()` output feeds **both** the prompt context and the citation chips, so the articles we cite are the articles the answer was actually built from.

### Reindexing

Django `post_save` / `post_delete` signals on `KnowledgeArticle` call `index_article()` / delete by `article_code`. Saving an article in the admin makes it searchable immediately — no command, no restart. `knowledgebase/apps.py` has a `ready()` that imports signals.

Management command `index_kb` with `--code <CODE>` and `--rebuild`.

---

## FILE 3 — `chatbot/services/ai_service.py` (orchestration)

`_uais_response()` flow:

```
search() → is_grounded() → filter_results() → _build_context()
    → call_llm(json_mode=True) → json.loads → _pick() validation
    → _chips_from_results() → AIResponse
```

Details that matter:

- **Not grounded** → `results` is emptied, so no chips are shown, and `UNGROUNDED_PREFIX` ("Note: this is general guidance, not from our knowledge base.") is prepended to the reply
- **`KB_STRICT_GROUNDING=True`** → skips the model entirely when ungrounded and returns `NOT_FOUND_REPLY`. Currently `False`, so ungrounded questions still get a labelled general answer
- **`_pick(value, allowed)`** validates the model's suggested category, priority and request type against allow-lists, returning `''` on no match. The model cannot introduce a classification value our form does not have
- **Chips come from `metadata['article_code']`**, looked up in the database with `prefetch_related('tickets')`. The LLM never sees the chip list
- **Invalid JSON from the model** falls back to returning the raw text rather than erroring
- **Gateway failure** returns a plain "temporarily unavailable" message; the analyst continues without the assistant

### PHI guard

A regex detector for the 18 HIPAA Safe Harbor identifiers sits **at the service layer, before the engine selection branch**. Position is the whole point: no current or future AI integration can bypass it.

It must run before retrieval, not after. The embedding model is local, but Chroma **persists to disk** — so PHI reaching retrieval would be written to `chroma_db/`, breaking the zero-PHI-at-rest guarantee. The verification for this is the absence of a `KB search` log line on a blocked request.

Blocked attempts are logged as event type and identifier category, never content. A compliance log that stores the identifier it blocked is worse than no log.

---

## THRESHOLDS — CURRENT VALUES AND CALIBRATION

In `.env`:

```
KB_GROUNDING_THRESHOLD=0.65
KB_CITATION_MARGIN=0.12
KB_RESULTS=4
KB_STRICT_GROUNDING=False
```

**These are cosine DISTANCE, not similarity.** `distance = 1 - similarity`, so **lower is better** and the threshold is a ceiling, not a floor. 0.238 is a strong match; 0.772 is a poor one.

### Calibration data measured so far

| Query | Distance | Correct behaviour? |
|---|---|---|
| "client user cannot sign in, account not recognised" | 0.348 | grounded ✅ |
| "how do I get access for salesforce" | 0.238 | grounded ✅ |
| "FSSO" (single acronym) | 0.582 | grounded ✅ — was wrongly rejected at 0.55, which is why the threshold is 0.65 |
| "how do I export a report to excel" | 0.772 | correctly ungrounded ✅ |

Single-acronym queries are the weakest possible input and score far worse than sentences. Real analyst questions are sentences.

### Threshold discipline — please respect this

**Do not tune a threshold to compensate for malformed content.** It bakes the defect into the config permanently, and every well-formed article added afterwards gets judged by a threshold calibrated against the worst one.

We hit this exactly. A query returned four hits spanning 0.238 to 0.283 — a 0.045 spread across three articles, effectively tied. Tightening `CITATION_MARGIN` to separate them would have required 0.005, and would have cited the *wrong* article, because the correct article ranked third purely because it had no headings. The fix was content, not configuration.

---

## DESIGN PRINCIPLES ESTABLISHED — DO NOT REGRESS THESE

1. **Content lives in the database, never in code.** An earlier version had knowledge base articles hardcoded in a `KNOWLEDGE` list in `ai_service.py` and a `seed_kb.py` management command. Both were deleted. Articles are authored in Django admin and exported to a fixture for portability. Never propose putting article content back in a Python file.
2. **Citations are mechanical, never model-chosen.**
3. **Article codes are auto-generated** as `{PRODUCT}-{CATEGORY_ABBREV}-{NNN}`, read-only after creation. Human-typed codes drift.
4. **Product codes resolve case-insensitively** through `canonical_code()`, which uses an uppercase lookup dict because registry keys are mixed case (`eCAC`, `pCAC`).
5. **No PHI in logs, no prompt or response content in logs.**
6. **Nothing the AI suggests is applied automatically.** Every suggestion requires an explicit click.
7. **Article detail URLs stay flat** at `/kb/article/<code>/`, independent of the browse hierarchy, so links already pasted into Salesforce cases keep working.

---

## CURRENT STATE — WHAT IS VERIFIED WORKING

- Live UAIS calls succeed, roughly 1.8–3.9s, ~1450 prompt tokens for four chunks
- Grounded answers demonstrably contradict the model's untrained instinct where our runbooks do
- Admin authoring loop: save an article, the signal reindexes it, it is searchable immediately with no restart
- Chips render the correct article and its linked Salesforce case
- Cross-product discrimination works — OCC and CCC questions return the right product's articles
- `filter_results()` is in place on the live path

---

## OPEN ITEMS, IN PRIORITY ORDER

### 1. Add section headings to `OCC-ONB-001`

That article logs as `OCC-ONB-001/Section`, meaning no headings were detected and it was chunked by paragraph. It therefore ranks third on a Salesforce-access question behind two user-management articles, despite being the correct answer, and all three get cited.

Fix in admin: add headings on their own lines, each ending in a colon — `Purpose:`, `Who Can Request Access:`, `Prerequisites:`, `Requesting Salesforce Access:`, `After Access Is Granted:`, and `Step N:` for procedural steps. The heading text is embedded as `Section: <heading>`, so a heading containing the query's own vocabulary is legitimate signal, not gaming.

**Expected after the fix:** `OCC-ONB-001` lands around 0.15–0.19 and leads clearly; the existing 0.12 margin then drops the other two articles with no config change. Re-measure before changing any threshold.

### 2. Metadata filtering with `where` — the scale fix

`search()` already accepts a `where` parameter and **nothing currently passes it.** This is the largest unused lever.

The problem it solves: as the corpus grows, many articles across all products will contain boilerplate like "must be documented in a Salesforce case." Forty articles containing that line means forty genuinely-similar chunks, and no distance cutoff separates forty true near-matches. This is a scoping problem, not a ranking problem.

Chroma filters on metadata *before* computing distances, and `product_code` and `category` are already stored on every chunk. The case form knows the product, so a question asked from an OCC case should search OCC chunks only — the searched corpus then stays the size of one product's articles regardless of total KB size.

From the chat landing page the product is not known, but `expand_query()` already detects product aliases; the same detection can set the filter when a product is named and search broadly when it is not.

### 3. Do not duplicate boilerplate across articles

Policy text repeated in every article is what creates the collision. State it once.

### 4. Group by article when citing

Rank articles by their best chunk and cite the top one or two, rather than citing every article represented in the result set. Caps chip noise independent of corpus size.

### 5. Test the PHI guard end to end

Not yet run on the live path. Put an identifier in the description field where it does not belong, trigger the AI panel, confirm the block — and confirm **no `KB search` line appears in the log**, which is what proves the guard sits before retrieval.

### 6. Check the mock path for the same citation flaw

`_mock_response()` builds its own chips. If it calls `kb_index.search()` without `filter_results()`, it has the over-broad citation bug that was just fixed on the live path. The mock path is what runs with `UAIS_ENABLED=False`, which is the demo configuration — so this would surface in front of an audience while the live path was clean.

---

## REJECTED APPROACHES — DO NOT RE-PROPOSE

- **Async LLM calls.** Removed in favour of sync; Django's request path is sync.
- **Automatic retry on failed case submission.** Removed deliberately — retry requires retaining PHI.
- **Hardcoded knowledge base content.** Deleted twice. Content belongs in the database.
- **Hiding empty product tiles in the browse.** An empty tile is visible coverage information and doubles as an authoring checklist.
- **Lowering `KB_RESULTS`.** The retrieval problems encountered were never caused by volume; ~1450 prompt tokens for four chunks is healthy.

---

## DIAGNOSTIC LOGGING — READ THESE TWO LINES FIRST

Every retrieval question is answered by these:

```
INFO chatbot.services.kb_index: KB search: 4 hits — OCC-UM-001/Prerequisites 0.238, OCC-UM-001/Step 5: Add the new user: 0.243, OCC-ONB-001/Section 0.267, OCC-UM-002/Step 1: Verify OCC Account Status 0.283
INFO chatbot.services.kb_index: KB filter: kept 4 of 4 (best 0.238, cutoff 0.358) — OCC-UM-001, OCC-UM-001, OCC-ONB-001, OCC-UM-002
```

Both log unconditionally. The filter log deliberately fires even when it drops nothing, because a filter that logs only when it acts is indistinguishable from a filter that is not wired up — that ambiguity cost us a debugging round trip.

When diagnosing retrieval, ask me for these two lines before proposing anything.