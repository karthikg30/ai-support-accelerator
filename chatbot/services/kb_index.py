"""
Knowledge base vector index.

Chunks articles on their section headings, prepends a context header so
each chunk is self-describing, and stores them in a persistent Chroma
collection.

Django is the source of truth. This index is derived data, rebuilt with
`python manage.py index_kb`. Never edit it directly.
"""

import logging
import re
import threading

import chromadb
from decouple import config
from django.conf import settings

from .product_registry import get_product

logger = logging.getLogger(__name__)

INDEX_PATH = config('KB_INDEX_PATH', default='chroma_db')
GROUNDING_THRESHOLD = config('KB_GROUNDING_THRESHOLD', default=0.60, cast=float)
DEFAULT_RESULTS = config('KB_RESULTS', default=4, cast=int)

COLLECTION_NAME = 'knowledge_base'

# A section heading is either "Something:" on its own line, or "Step 3 - ..."
SECTION_RE = re.compile(
    r'^(?P<heading>(?:Step\s+\d+[^\n]{0,80})|(?:[A-Z][^:\n]{2,70}:))\s*$',
    re.MULTILINE,
)

_client = None
_collection = None
_lock = threading.Lock()


# ----------------------------------------------------------------------
# Collection
# ----------------------------------------------------------------------

def get_collection():
    """Persistent Chroma collection, created on first use."""
    global _client, _collection

    if _collection is not None:
        return _collection

    with _lock:
        if _collection is None:
            path = str(settings.BASE_DIR / INDEX_PATH)
            _client = chromadb.PersistentClient(path=path)
            _collection = _client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={'hnsw:space': 'cosine'},
            )
            logger.info('KB index ready at %s', path)

    return _collection


# ----------------------------------------------------------------------
# Chunking
# ----------------------------------------------------------------------

def split_sections(content):
    """Return a list of (heading, body) pairs.

    Splits on section headings where the article has them, and falls back
    to paragraph grouping where it does not.
    """
    content = (content or '').strip()
    if not content:
        return []

    matches = list(SECTION_RE.finditer(content))

    if len(matches) < 2:
        return _paragraph_chunks(content)

    sections = []

    preamble = content[:matches[0].start()].strip()
    if preamble:
        sections.append(('Overview', preamble))

    for i, match in enumerate(matches):
        heading = match.group('heading').rstrip(':').strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        if body:
            sections.append((heading, body))

    return sections


def _paragraph_chunks(content, target_chars=800):
    """Group paragraphs into chunks of roughly target_chars."""
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

    chunks = []
    current = []
    size = 0

    for paragraph in paragraphs:
        if size + len(paragraph) > target_chars and current:
            chunks.append(('Section', '\n\n'.join(current)))
            current, size = [], 0
        current.append(paragraph)
        size += len(paragraph)

    if current:
        chunks.append(('Section', '\n\n'.join(current)))

    return chunks


def build_header(product, article, section):
    """Context header prepended to every chunk before embedding.

    This is what makes a chunk self-describing, and what puts the product
    shorthands into the embedded text so "ECC" matches.
    """
    lines = []

    if product['name']:
        aliases = ', '.join(product['aliases'])
        lines.append(f"Product: {product['name']} ({aliases})")

    lines.append(f"Category: {article.get_category_display()}")
    lines.append(f"Article: {article.code} - {article.title}")
    lines.append(f"Section: {section}")

    return '\n'.join(lines)


# ----------------------------------------------------------------------
# Indexing
# ----------------------------------------------------------------------

def index_article(article):
    """Re-index a single article. Returns the number of chunks written."""
    collection = get_collection()
    product = get_product(article.product_code)

    # Clear existing chunks first — an edited article may have fewer
    # sections, and orphans would keep being retrieved.
    try:
        collection.delete(where={'article_code': article.code})
    except Exception as exc:
        logger.warning('Could not clear chunks for %s: %s', article.code, exc)

    sections = split_sections(article.content)
    if not sections:
        return 0

    ids, documents, metadatas = [], [], []

    for i, (heading, body) in enumerate(sections):
        header = build_header(product, article, heading)
        ids.append(f'{article.code}-{i:03d}')
        documents.append(f'{header}\n\n{body}')
        metadatas.append({
            'article_code': article.code,
            'article_title': article.title,
            'product_code': (article.product_code or '').upper(),
            'category': article.category,
            'section': heading,
        })

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def clear_index():
    """Drop the whole collection. Used by index_kb --rebuild."""
    global _collection

    collection = get_collection()
    existing = collection.get(include=[])
    if existing and existing.get('ids'):
        collection.delete(ids=existing['ids'])

    logger.info('KB index cleared')


# ----------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------

def expand_query(text):
    """Append full product names when a shorthand appears in the query.

    "ECC login issue" becomes "ECC login issue Enterprise Computer-Assisted
    Coding", so the query embedding lands near chunks whose header names
    that product.
    """
    lowered = (text or '').lower()
    additions = []

    from .product_registry import PRODUCT_REGISTRY

    for code, product in PRODUCT_REGISTRY.items():
        candidates = [code] + product['aliases']
        for candidate in candidates:
            if re.search(r'\b' + re.escape(candidate.lower()) + r'\b', lowered):
                additions.append(product['name'])
                break

    if additions:
        return f"{text} {' '.join(additions)}"
    return text


def search(question, n_results=None, where=None):
    """Return a list of {document, metadata, distance}, nearest first."""
    n_results = n_results or DEFAULT_RESULTS
    collection = get_collection()

    expanded = expand_query(question)

    try:
        raw = collection.query(
            query_texts=[expanded],
            n_results=n_results,
            where=where,
        )
    except Exception as exc:
        logger.error('KB search failed: %s', exc)
        return []

    documents = (raw.get('documents') or [[]])[0]
    metadatas = (raw.get('metadatas') or [[]])[0]
    distances = (raw.get('distances') or [[]])[0]

    results = [
        {'document': d, 'metadata': m, 'distance': dist}
        for d, m, dist in zip(documents, metadatas, distances)
    ]

    if results:
        logger.info(
            'KB search: %d hits — %s',
            len(results),
            ', '.join(
                f"{h['metadata'].get('article_code')}/"
                f"{h['metadata'].get('section')} {h['distance']:.3f}"
                for h in results
            ),
        )
    else:
        logger.info('KB search: no hits')

    return results


def is_grounded(results):
    """True when the best match is close enough to answer from."""
    return bool(results) and results[0]['distance'] <= GROUNDING_THRESHOLD

CITATION_MARGIN = config('KB_CITATION_MARGIN', default=0.12, cast=float)


def filter_results(results):
    """
    Narrow a result set to the hits that genuinely belong to the best match.

    Two caps, both needed:
      - absolute: never keep a hit the grounding rule would have rejected
      - relative: never keep a hit much worse than the best one, because a
        query's best distance varies hugely with phrasing length

    Used for both prompt context and citation chips, so the articles we cite
    are the articles the answer was actually built from.
    """
    if not results:
        return []

    best = results[0]['distance']
    cutoff = min(GROUNDING_THRESHOLD, best + CITATION_MARGIN)
    kept = [r for r in results if r['distance'] <= cutoff]

    logger.info(
        'KB filter: kept %d of %d (best %.3f, cutoff %.3f) — %s',
        len(kept), len(results), best, cutoff,
        ', '.join(r['metadata'].get('article_code') for r in kept),
    )

    return kept

MAX_ARTICLES = config('KB_MAX_ARTICLES', default=2, cast=int)


def top_articles(results):
    """
    Group filtered hits by article and rank each article by its best chunk.

    filter_results() has already applied the distance margin, so this only
    groups and caps. It adds no new threshold. The caller sends the FULL
    text of these articles to the model, so a procedure is never answered
    from fragments.

    Logs codes and distances only, never content. Always logs.
    """
    best = {}
    for r in results:
        code = r['metadata'].get('article_code')
        if code and (code not in best or r['distance'] < best[code]):
            best[code] = r['distance']

    ranked = sorted(best.items(), key=lambda kv: kv[1])
    kept = [code for code, _ in ranked[:MAX_ARTICLES]]

    logger.info(
        'KB articles: kept %d of %d (max %d) — %s',
        len(kept), len(ranked), MAX_ARTICLES,
        ', '.join(f'{c} {d:.3f}' for c, d in ranked) or 'none',
    )
    return kept