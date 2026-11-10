"""
KB tuning runner. Reads kb_tuning_set.csv, runs each question through the SAME
retrieval path the app uses (product scope + metadata filter + Chroma search),
and prints the best distance per question. It never calls the LLM, so it costs
no tokens.

Run from the project root (same folder as manage.py):
    python manage.py shell -c "exec(open('tune_kb.py').read())"

Writes kb_tuning_results.csv next to the input file.
"""
import csv

from decouple import config

from chatbot.services import kb_index
from chatbot.services.ai_service import _retrieval_filter, _scope_products

SRC = 'kb_tuning_set.csv'
OUT = 'kb_tuning_results.csv'

cur_threshold = config('KB_GROUNDING_THRESHOLD', default=0.45, cast=float)
cur_margin = config('KB_CITATION_MARGIN', default=0.12, cast=float)

with open(SRC, newline='', encoding='utf-8-sig') as fh:
    test_rows = list(csv.DictReader(fh))

results = []
for r in test_rows:
    prior = (r.get('prior_question') or '').strip()
    question = r['question'].strip()
    history = [{'role': 'user', 'content': prior}] if prior else []
    search_text = '\n'.join(([prior] if prior else []) + [question])

    scope = _scope_products(question, history)
    hits = kb_index.search(search_text, where=_retrieval_filter(scope))

    best = min((h['distance'] for h in hits), default=None)

    # Best distance per article, nearest first.
    per_article = {}
    for h in hits:
        code = h['metadata'].get('article_code', '?')
        per_article[code] = min(per_article.get(code, 9.0), h['distance'])
    ranked = sorted(per_article.items(), key=lambda kv: kv[1])

    expected = [a.strip() for a in (r.get('expected_articles') or '').split('|') if a.strip()]
    exp_gaps = [per_article[a] - best for a in expected if a in per_article and best is not None]
    extra_gaps = [d - best for a, d in ranked if a not in expected and best is not None] if expected else []
    missing = [a for a in expected if a not in per_article]

    results.append({
        'id': r['id'],
        'group': r['group'],
        'expected': r['expected_outcome'],
        'scope': ','.join(scope),
        'best': best,
        'top_article': ranked[0][0] if ranked else '',
        'articles': '; '.join(f'{a} {d:.3f}' for a, d in ranked),
        'exp_gaps': exp_gaps,
        'extra_gaps': extra_gaps,
        'missing': missing,
        'question': question,
    })

# ---- Per-question table -------------------------------------------------
print()
print(f'Current settings: threshold={cur_threshold}  margin={cur_margin}')
print()
print(f"{'id':>3} {'group':<13} {'expect':<7} {'best':>6} {'now':<7} {'scope':<6} top article / note")
for x in results:
    best = x['best']
    now = 'answer' if (best is not None and best <= cur_threshold) else 'refuse'
    flag = ''
    if x['expected'] in ('answer', 'refuse') and now != x['expected']:
        flag = '  <-- MISMATCH'
    if x['missing']:
        flag += f"  (expected article not in hits: {', '.join(x['missing'])})"
    best_txt = f'{best:.3f}' if best is not None else '  none'
    print(f"{x['id']:>3} {x['group']:<13} {x['expected']:<7} {best_txt:>6} {now:<7} {x['scope']:<6} {x['top_article']}{flag}")

# ---- Suggested threshold ------------------------------------------------
ans = [x for x in results if x['expected'] == 'answer' and x['best'] is not None]
ref = [x for x in results if x['expected'] == 'refuse']
ref_scores = [x['best'] if x['best'] is not None else 9.0 for x in ref]

print()
print('THRESHOLD')
if ans and ref_scores:
    worst_ans = max(ans, key=lambda x: x['best'])
    lo_ref = min(ref, key=lambda x: x['best'] if x['best'] is not None else 9.0)
    a = worst_ans['best']
    b = lo_ref['best'] if lo_ref['best'] is not None else 9.0
    print(f"  Highest in-scope best distance : {a:.3f}  (id {worst_ans['id']}: {worst_ans['question'][:60]})")
    print(f"  Lowest off-topic best distance : {b:.3f}  (id {lo_ref['id']}: {lo_ref['question'][:60]})")
    if a < b:
        print(f'  Clean gap. Suggested threshold  : {round((a + b) / 2, 2)}')
    else:
        print('  OVERLAP: some off-topic questions score closer than some in-scope ones.')
        print('  Fix the retrieval or the articles for those ids, do not just move the threshold.')
else:
    print('  Not enough answer/refuse rows to calculate.')

# ---- Suggested margin ---------------------------------------------------
need = [g for x in results for g in x['exp_gaps']]
drop = [g for x in results for g in x['extra_gaps']]
print()
print('CITATION MARGIN')
if need:
    print(f'  Largest gap of an expected article : {max(need):.3f}  (margin must be at least this)')
if drop:
    print(f'  Smallest gap of an unwanted article: {min(drop):.3f}  (margin must be below this)')
if need and drop:
    if max(need) < min(drop):
        print(f'  Suggested margin                   : {round((max(need) + min(drop)) / 2, 2)}')
    else:
        print('  OVERLAP: an unwanted article sits closer than a needed one. Margin alone cannot fix it.')

# ---- Save ---------------------------------------------------------------
with open(OUT, 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.writer(fh)
    w.writerow(['id', 'group', 'expected', 'scope', 'best_distance', 'top_article', 'articles_and_distances', 'question'])
    for x in results:
        w.writerow([x['id'], x['group'], x['expected'], x['scope'],
                    '' if x['best'] is None else f"{x['best']:.3f}",
                    x['top_article'], x['articles'], x['question']])
print()
print(f'Saved {OUT}')
