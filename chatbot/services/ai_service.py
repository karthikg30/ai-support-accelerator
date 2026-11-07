"""
AI assistant service layer.

MVP: keyword-matched mock responses so the full UX can be built
and demoed without a live LLM.

TODO(uais): implement `_uais_response()` once integration details are
confirmed with the platform team:
  - Interface: internal package / REST endpoint / Python client?
  - Auth: API key, Azure AD token, or managed identity? (goes in .env)
  - Response format: structured JSON, or free text needing parsing?
  - Reachable from local dev, or Azure-only?
Nothing outside this file should need to change when it is swapped in.
"""

from decouple import config
from . import phi_guard
import json
import re

import json
import logging

from . import phi_guard, uais_client
from . import kb_index

logger = logging.getLogger(__name__)

SALESFORCE_CASE_BASE_URL = config(
    'SALESFORCE_CASE_BASE_URL',
    default='https://example.lightning.force.com/lightning/r/Case'
)
UAIS_ENABLED = config('UAIS_ENABLED', default=False, cast=bool)

MAX_MESSAGE_LENGTH = 2000

STRICT_GROUNDING = config('KB_STRICT_GROUNDING', default=False, cast=bool)

class AIResponse:
    """Uniform response shape, whether mock or live."""

    def __init__(self, reply, suggested_category='', suggested_priority='',
                 suggested_request_type='', related_articles=None,
                 similar_cases=None, engine='mock'):
        self.reply = reply
        self.suggested_category = suggested_category
        self.suggested_priority = suggested_priority
        self.suggested_request_type = suggested_request_type
        self.related_articles = related_articles or []
        self.similar_cases = similar_cases or []
        self.engine = engine

    def to_dict(self):
        return {
            'reply': self.reply,
            'suggested_category': self.suggested_category,
            'suggested_priority': self.suggested_priority,
            'suggested_request_type': self.suggested_request_type,
            'related_articles': self.related_articles,
            'similar_cases': self.similar_cases,
        }


class PHIBlocked(Exception):
    """Raised when a PHI guardrail prevents an LLM call."""

    def __init__(self, labels):
        self.labels = labels
        super().__init__('PHI detected')


def get_ai_response(message, user=None, history=None):
    """Entry point used by views. Returns an AIResponse."""
    message = (message or '').strip()[:MAX_MESSAGE_LENGTH]

    if not message:
        return AIResponse(reply="Please type a question and I'll help.")

    labels = phi_guard.scan(message)
    if labels:
        raise PHIBlocked(labels)

    history = _safe_history(history)

    if UAIS_ENABLED:
        return _uais_response(message, user, history=history)
    return _mock_response(message)


def _safe_history(history):
    """Second PHI check on earlier turns before they leave the app.

    Turns flagged by the PHI guard are dropped, not sent. Only the count
    is logged, never the content.
    """
    safe = []
    dropped = 0
    for turn in history or []:
        role = turn.get('role')
        content = (turn.get('content') or '').strip()
        if role not in ('user', 'assistant') or not content:
            continue
        if phi_guard.scan(content):
            dropped += 1
            continue
        safe.append({'role': role, 'content': content})

    if dropped:
        logger.warning(
            'Chat history: dropped %d turn(s) flagged by the PHI guard', dropped
        )
    return safe


# ----------------------------------------------------------------------
# Mock engine
# ----------------------------------------------------------------------
GUIDANCE = {
    'what information': (
        "Before creating a case, collect:\n"
        "1. Account and contact details\n"
        "2. A clear one-line summary of the issue\n"
        "3. When it started and how many users are affected\n"
        "4. Exact error messages or screenshots\n"
        "5. Steps already attempted\n"
        "6. Whether PHI is involved"
    ),
    'classify': (
        "To classify an issue:\n"
        "1. Identify the product the user is working in\n"
        "2. Decide whether it is access, data, or functionality\n"
        "3. Set priority by impact: a single user is usually Medium, "
        "multiple users or a whole site is High, and anything with a "
        "security, privacy or patient-safety impact is Critical"
    ),
    'escalat': (
        "Escalate when:\n"
        "1. The documented troubleshooting steps are exhausted\n"
        "2. Multiple users or a whole site is affected\n"
        "3. There is a security, privacy, or patient-safety concern\n"
        "4. The issue exceeds the Tier-1 resolution window\n"
        "Include what you have already tried in the escalation notes."
    ),
}

def _mock_response(message):
    """Fallback when UAIS is disabled.

    Uses the same retrieval the live path uses, but returns the matching
    passage raw instead of having a model rewrite it. No hardcoded
    knowledge — the database is the only source.
    """
    lowered = message.lower()

    for phrase, text in GUIDANCE.items():
        if phrase in lowered:
            return AIResponse(reply=text)

    results = kb_index.search(message)

    if kb_index.is_grounded(results):
        top = results[0]
        related_articles, similar_cases = _chips_from_results(results)
        return AIResponse(
            reply=f"[Retrieval only - no model connected]\n\n{top['document']}",
            related_articles=related_articles,
            similar_cases=similar_cases,
        )

    return AIResponse(
        reply=(
            "I don't have anything in the knowledge base that covers this. "
            "Try rephrasing, or describe the product and the symptom."
        )
    )


# ----------------------------------------------------------------------
# UAIS engine
# ----------------------------------------------------------------------

VALID_CATEGORIES = [
    'User Management', 'Patient Portal', 'Claims', 'Enrollment',
    'Provider Access', 'Technical Issues', 'Account Management', 'Security',
]

VALID_PRIORITIES = ['Low', 'Medium', 'High', 'Critical']

VALID_REQUEST_TYPES = [
    'Technical Issue', 'Access Request', 'Claims Inquiry',
    'Enrollment Request', 'Provider Support', 'Security Inquiry',
]

UNGROUNDED_PREFIX = (
    "Note: this is general guidance, not from our knowledge base.\n\n"
)

NOT_FOUND_REPLY = (
    "I don't have anything in the knowledge base that covers this. "
    "Try rephrasing, or check with Tier 2 if it's urgent."
)

_SHARED_RULES = """Rules:
- Never include patient identifiers in your reply.
- Earlier messages in this conversation are context only. Use them to \
understand what the agent is referring to, but never treat an earlier reply \
as a source of facts, steps, values or URLs.
- Choose suggested_category, suggested_priority and suggested_request_type \
ONLY from the allowed values below. If none fit, use an empty string.

Allowed suggested_category: {categories}
Allowed suggested_priority: {priorities}
Allowed suggested_request_type: {request_types}

Priority guidance: a single affected user is usually Medium, multiple users \
or a whole site is High, and anything with a security, privacy or \
patient-safety impact is Critical.

Respond with exactly this json shape:
{{
  "reply": "your guidance as plain text, using short lines or numbered steps",
  "suggested_category": "",
  "suggested_priority": "",
  "suggested_request_type": ""
}}"""

GROUNDED_PROMPT = """You are a Tier-1 support assistant for a healthcare \
technology company.

Answer the agent's question using ONLY the knowledge base extracts below.

Grounding rules:
- Base your answer only on the extracts. Do not add steps, tools, system \
names, URLs or procedures that do not appear in them.
- If an extract is a step-by-step procedure, list ALL of its steps in \
order. Do not skip, merge or shorten steps, even if the question seems to \
need only part of the procedure.
- Copy exact values from the extracts word for word: numbers and limits, \
URLs, email addresses, email subjects, field names, field values, role \
names and team names. You may shorten the sentence around a value, but \
never replace a value with a vague phrase such as "the correct URL" or \
"near the limit".
- Prefer the exact wording of the extracts over your own phrasing when \
describing a procedure.
- If the extracts only partly answer the question, answer only the part \
they cover, then say plainly which part is not covered in the knowledge \
base. Do NOT complete the missing part from general knowledge, and do not \
guess.

KNOWLEDGE BASE EXTRACTS
=======================
{context}
=======================

""" + _SHARED_RULES

UNGROUNDED_PROMPT = """You are a Tier-1 support assistant for a healthcare \
technology company.

Nothing in the knowledge base matched this question, so answer from general \
support knowledge.

- Do NOT invent company-specific details: internal tool names, URLs, system \
names, team names, ticket numbers, or procedures you have not been told about.
- Keep the guidance general and say plainly where the agent would need to \
check local documentation.

""" + _SHARED_RULES


def _build_system_prompt(context=None):
    template = GROUNDED_PROMPT if context else UNGROUNDED_PROMPT
    return template.format(
        context=context or '',
        categories=' | '.join(VALID_CATEGORIES),
        priorities=' | '.join(VALID_PRIORITIES),
        request_types=' | '.join(VALID_REQUEST_TYPES),
    )


def _pick(value, allowed):
    """Return the value only if it matches an allowed option, else ''."""
    if not value:
        return ''
    value = str(value).strip()
    for option in allowed:
        if value.lower() == option.lower():
            return option
    return ''

def _build_context(results):
    """Join retrieved chunks into the prompt context block.

    Each chunk already carries its own header (product, article, section),
    so the model can see where every passage came from.
    """
    return '\n\n---\n\n'.join(hit['document'] for hit in results)

def _build_article_context(codes):
    """Full text of the selected articles, in ranking order.

    Chunks are used to FIND the article; the whole article is used to
    ANSWER, so multi-step procedures reach the model complete.
    """
    from knowledgebase.models import KnowledgeArticle

    articles = {
        a.code: a for a in KnowledgeArticle.objects.filter(code__in=codes)
    }
    blocks = []
    for code in codes:
        a = articles.get(code)
        if a:
            blocks.append(
                f'Article: {a.code} - {a.title}\n'
                f'Category: {a.get_category_display()}\n\n'
                f'{a.content}'
            )
    return '\n\n---\n\n'.join(blocks)

def _chips_from_results(results):
    """Derive article and case chips from what retrieval actually returned.

    Article codes come from chunk metadata; tickets are read from the
    article itself, so ticket links can change without re-indexing.
    """
    codes = list(dict.fromkeys(
        hit['metadata'].get('article_code')
        for hit in results
        if hit['metadata'].get('article_code')
    ))
    if not codes:
        return [], []

    from knowledgebase.models import KnowledgeArticle

    articles = {
        a.code: a
        for a in KnowledgeArticle.objects.filter(
            code__in=codes
        ).prefetch_related('tickets')
    }

    related_articles = [code for code in codes if code in articles]

    similar_cases = []
    seen = set()
    for code in related_articles:
        for ticket in articles[code].tickets.all():
            if ticket.number not in seen:
                seen.add(ticket.number)
                similar_cases.append({
                    'number': ticket.number,
                    'url': ticket.url,
                    'label': ticket.label,
                })

    return related_articles, similar_cases

def _products_named(text):
    """Product codes mentioned in the text, by code or alias (for example OPA)."""
    from .product_registry import get_registry

    lowered = (text or '').lower()
    found = []
    for code, data in get_registry().items():
        for term in [code] + list(data['aliases']):
            if re.search(r'\b' + re.escape(term.lower()) + r'\b', lowered):
                found.append(code)
                break
    return found


def _scope_products(message, history):
    """Product named in this question, else the latest one named earlier in the chat."""
    named = _products_named(message)
    if named:
        return named
    for turn in reversed(history or []):
        if turn['role'] == 'user':
            named = _products_named(turn['content'])
            if named:
                return named
    return []

def _retrieval_filter(products=None):
    """Chroma filter: keep retired products and categories out, and optionally
    restrict the search to the products named in the question."""
    try:
        from knowledgebase.models import KBCategory, KBProduct

        inactive_products = [
            c.upper()
            for c in KBProduct.objects.filter(active=False).values_list('code', flat=True)
        ]
        inactive_categories = list(
            KBCategory.objects.filter(active=False).values_list('key', flat=True)
        )
    except Exception:
        return None

    clauses = []
    if products:
        clauses.append({'product_code': {'$in': [p.upper() for p in products]}})
    if inactive_products:
        clauses.append({'product_code': {'$nin': inactive_products}})
    if inactive_categories:
        clauses.append({'category': {'$nin': inactive_categories}})

    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {'$and': clauses}
# ----------------------------------------------------------------------
# UAIS engine (not yet implemented)
# ----------------------------------------------------------------------

def _uais_response(message, user=None, history=None):
    """Live response from UAIS, grounded in retrieved knowledge base chunks."""
    history = history or []

    # A follow-up like "and for BCNC users?" has no topic of its own, so the
    # previous question is added to the search text. The model still gets
    # the current message as the question.
    previous = [t['content'] for t in history if t['role'] == 'user']
    search_text = '\n'.join(previous + [message])
    logger.info(
        'KB query: %s',
        f'current + {len(previous)} previous question(s)'
        if previous else 'current question only',
    )

    scope = _scope_products(message, history)
    if scope:
        logger.info('KB scope: product filter %s', ', '.join(scope))
    results = kb_index.search(search_text, where=_retrieval_filter(scope))
    grounded = kb_index.is_grounded(results)

    context = None
    if grounded:
        # Chunks find the article; the full article answers.
        results = kb_index.filter_results(results)
        codes = kb_index.top_articles(results)

        # Chips must describe exactly the articles in the prompt.
        results = [
            r for r in results
            if r['metadata'].get('article_code') in codes
        ]

        context = _build_article_context(codes) or _build_context(results)
    else:
        results = []
        if STRICT_GROUNDING:
            logger.info('No grounded match; strict mode, skipping the model')
            return AIResponse(reply=NOT_FOUND_REPLY, engine='uais')

    try:
        raw = uais_client.call_llm(
            prompt=message,
            system=_build_system_prompt(context=context),
            json_mode=True,
            history=history,
        )
    except uais_client.UAISError as exc:
        logger.error('UAIS unavailable: %s', exc)
        return AIResponse(
            reply=(
                'The assistant is temporarily unavailable. Please try again '
                'in a moment, or continue without it.'
            ),
            engine='uais',
        )

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning('UAIS returned content that was not valid JSON')
        return AIResponse(reply=raw.strip(), engine='uais')

    reply = (data.get('reply') or '').strip()
    if reply and not grounded:
        reply = UNGROUNDED_PREFIX + reply

    related_articles, similar_cases = _chips_from_results(results)

    return AIResponse(
        reply=reply,
        suggested_category=_pick(data.get('suggested_category'), VALID_CATEGORIES),
        suggested_priority=_pick(data.get('suggested_priority'), VALID_PRIORITIES),
        suggested_request_type=_pick(
            data.get('suggested_request_type'), VALID_REQUEST_TYPES
        ),
        related_articles=related_articles,
        similar_cases=similar_cases,
        engine='uais',
    )
# ----------------------------------------------------------------------
# Rephrase
# ----------------------------------------------------------------------

MAX_REPHRASE_LENGTH = 4000

# TODO(uais): PHI SAFETY — before enabling live rephrasing, confirm that
# case descriptions may be sent to the model at all. Descriptions can
# contain PHI. Required decisions:
#   - Is the UAIS endpoint covered by a BAA / approved for PHI?
#   - If not, block rephrase when includes_phi is Yes, or redact first.
#   - Confirm retention: is the submitted text logged by the provider?
# Do not enable UAIS_ENABLED for rephrase until this is answered.


class RephraseResult:
    def __init__(self, success, text='', note='', error='', engine='mock'):
        self.success = success
        self.text = text
        self.note = note
        self.error = error
        self.engine = engine

    def to_dict(self):
        return {
            'success': self.success,
            'text': self.text,
            'note': self.note,
            'error': self.error,
        }


def rephrase_text(text, user=None):
    """Improve the wording of a case description. Returns a RephraseResult."""
    text = (text or '').strip()

    if len(text) < 20:
        return RephraseResult(
            success=False,
            error='Please write a little more before rephrasing.',
        )

    text = text[:MAX_REPHRASE_LENGTH]

    labels = phi_guard.scan(text)
    if labels:
        raise PHIBlocked(labels)

    if UAIS_ENABLED:
        return _rephrase_uais(text, user)
    return _rephrase_mock(text)


def _rephrase_mock(text):
    """Light, honest cleanup: spacing, capitalisation, punctuation."""
    import re

    cleaned = re.sub(r'[ \t]+', ' ', text)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'\s+([,.;:!?])', r'\1', cleaned)
    cleaned = re.sub(r'([,.;:!?])(?=[^\s\d])', r'\1 ', cleaned)

    lines = []
    for line in cleaned.split('\n'):
        line = line.strip()
        if not line:
            lines.append('')
            continue

        parts = re.split(r'(?<=[.!?])\s+', line)
        parts = [p[0].upper() + p[1:] if p else p for p in parts]
        line = ' '.join(parts)

        if line and line[-1] not in '.!?:':
            line += '.'
        lines.append(line)

    cleaned = '\n'.join(lines).strip()

    return RephraseResult(
        success=True,
        text=cleaned,
        note='Basic formatting cleanup. Full rephrasing activates once the '
             'AI service is connected.',
    )


def _rephrase_uais(text, user=None):
    """Not implemented yet. Falls back to the mock cleanup so the Rephrase
    button keeps working while UAIS is enabled for chat."""
    logger.info('UAIS rephrase not implemented; using mock cleanup')
    return _rephrase_mock(text)