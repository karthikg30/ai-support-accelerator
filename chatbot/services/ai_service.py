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


def get_ai_response(message, user=None):
    """Entry point used by views. Returns an AIResponse."""
    message = (message or '').strip()[:MAX_MESSAGE_LENGTH]

    if not message:
        return AIResponse(reply="Please type a question and I'll help.")

    labels = phi_guard.scan(message)
    if labels:
        raise PHIBlocked(labels)

    if UAIS_ENABLED:
        return _uais_response(message, user)
    return _mock_response(message)


# ----------------------------------------------------------------------
# Mock engine
# ----------------------------------------------------------------------

KNOWLEDGE = [
        {
        'keywords': ['fsso', 'federated', 'single sign-on', 'wrong url', 'wrong link',
                     'standard url', 'not recognised', 'not recognized',
                     'not authorised', 'not authorized', 'unable to sign in',
                     'cannot sign in', 'signing in', 'sign-in fail'],
        'category': 'User Management',
        'request_type': 'Access Request',
        'priority': 'High',
        'causes': [
            'Client is federated and the user was sent the standard URL',
            'FSSO code missing or incorrect in the link the user opened',
            'Client FSSO status not confirmed before the link was sent',
        ],
        'steps': [
            'Ask the user to paste the exact link they opened',
            'Check whether the client is configured for FSSO',
            'If federated, send the client-specific FSSO URL instead',
            'Do not reset the password — the account is healthy, the routing is wrong',
            'Confirm other users at the same client received the correct link',
        ],
        'articles': ['KB1016', 'KB1015'],
        'tickets': [
            # TODO: replace `id` with the real Salesforce 18-character case ID
            {'number': '00856472', 'id': 'PLACEHOLDER_CASE_ID_1',
             'label': 'FSSO user could not sign in on standard URL'},
        ],
    },
    {
        'keywords': ['live training', 'training call', 'training session',
                     'during training', 'training support'],
        'category': 'User Management',
        'request_type': 'Access Request',
        'priority': 'High',
        'causes': [
            'Account created but registration not completed (status Invited)',
            'Client uses FSSO and was sent the standard URL',
            'Polaris email does not match the Galaxy email',
            'No Galaxy account was created before the session',
        ],
        'steps': [
            'Check whether the user has a Galaxy account at all',
            'If the account exists, check its status — Invited means registration is incomplete',
            'For Invited users, resend the registration link or paste it into the meeting chat',
            'For Active users, confirm FSSO status before sending any URL',
            'If still failing, check Polaris status and confirm the email matches Galaxy',
        ],
        'articles': ['KB1015', 'KB1016'],
        'tickets': [
            {'number': '00000002', 'id': 'PLACEHOLDER_CASE_ID_2',
             'label': 'Multiple users unable to access during training'},
        ],
    },
    {
        'keywords': ['galaxy', 'polaris', 'new user', 'provision', 'insight platform',
                     'identity provider', 'self service', 'provider id',
                     'mirror permissions', 'create account'],
        'category': 'User Management',
        'request_type': 'Access Request',
        'priority': 'Medium',
        'causes': [
            'New user account has not been provisioned in Galaxy',
            'Roles and permissions were not assigned after account creation',
            'Polaris identity missing or not linked to the Galaxy account',
            'Facility and specialty permissions not configured in Insight Platform',
        ],
        'steps': [
            'Check whether an existing user can be mirrored — this is the fastest route',
            'If not, confirm the client contracted modules in Salesforce under Account Notes',
            'Search Galaxy by name and email to rule out a duplicate account',
            'Create the user with the correct identity provider and role type',
            'Assign roles, then configure facilities and specialties in Insight Platform',
        ],
        'articles': ['KB1014', 'KB1015'],
        'tickets': [
            {'number': '00000003', 'id': 'PLACEHOLDER_CASE_ID_3',
             'label': 'New provider account provisioning request'},
        ],
    },
    {
        'keywords': ['portal', 'login', 'sign in', 'cannot access', 'lab result'],
        'category': 'Patient Portal',
        'request_type': 'Technical Issue',
        'priority': 'Medium',
        'causes': [
            'Browser cache or cookie issue',
            'User account locked or inactive',
            'Portal outage or degraded service',
        ],
        'steps': [
            'Clear browser cache and retry in a private window',
            'Verify the account status in the admin console',
            'Check the outage dashboard for active incidents',
            'Confirm VPN connectivity if accessing internally',
        ],
        'articles': ['KB1001', 'KB1002'],
    },
    {
        'keywords': ['password', 'reset', 'locked out', 'mfa', 'authenticator'],
        'category': 'Account Management',
        'request_type': 'Access Request',
        'priority': 'Medium',
        'causes': [
            'Too many failed sign-in attempts',
            'Expired password',
            'MFA device changed or unavailable',
        ],
        'steps': [
            'Confirm the user identity per verification policy',
            'Trigger a password reset from the admin console',
            'Re-register the MFA device if needed',
            'Ask the user to sign in and confirm access',
        ],
        'articles': ['KB1010', 'KB1011'],
    },
    {
        'keywords': ['claim', 'billing', 'payment', 'reimbursement', 'eob'],
        'category': 'Claims',
        'request_type': 'Claims Inquiry',
        'priority': 'High',
        'causes': [
            'Claim still in processing queue',
            'Missing or mismatched member information',
            'Coverage rule rejected the submission',
        ],
        'steps': [
            'Locate the claim by member ID and service date',
            'Check the current claim status and rejection code',
            'Verify member eligibility for the service date',
            'Escalate to the Claims team if the rejection is unclear',
        ],
        'articles': ['KB3006'],
    },
    {
        'keywords': ['enrollment', 'enroll', 'coverage', 'plan change', 'dependent'],
        'category': 'Enrollment',
        'request_type': 'Enrollment Request',
        'priority': 'Medium',
        'causes': [
            'Enrollment window has closed',
            'Missing supporting documentation',
            'Qualifying life event not yet recorded',
        ],
        'steps': [
            'Confirm the enrollment period applicable to the member',
            'Check for a recorded qualifying life event',
            'Collect any outstanding documentation',
            'Route to the Enrollment team for processing',
        ],
        'articles': ['KB1012'],
    },
    {
        'keywords': ['provider', 'directory', 'credential', 'network'],
        'category': 'Provider Access',
        'request_type': 'Provider Support',
        'priority': 'Medium',
        'causes': [
            'Provider record not yet synced',
            'Credentialing still in progress',
            'Incorrect network assignment',
        ],
        'steps': [
            'Search the provider directory by NPI',
            'Check the credentialing status',
            'Verify the network assignment on the contract',
            'Escalate to Provider Data Management if unresolved',
        ],
        'articles': ['KB3005'],
    },
    {
        'keywords': ['outage', 'down', 'slow', 'timeout', 'error 500', 'not loading'],
        'category': 'Technical Issues',
        'request_type': 'Technical Issue',
        'priority': 'High',
        'causes': [
            'Active service incident',
            'Network or connectivity problem',
            'Recent deployment causing regression',
        ],
        'steps': [
            'Check the outage dashboard for known incidents',
            'Confirm whether the issue affects multiple users',
            'Capture the exact error message and timestamp',
            'Escalate to Tier 2 with the collected evidence',
        ],
        'articles': 	['KB3004'],
    },
    {
        'keywords': ['phi', 'privacy', 'security', 'breach', 'hipaa'],
        'category': 'Security',
        'request_type': 'Security Inquiry',
        'priority': 'Critical',
        'causes': [
            'Potential unauthorized disclosure',
            'Uncertainty about handling requirements',
            'Data shared through an unapproved channel',
        ],
        'steps': [
            'Do not record further PHI in this case',
            'Follow the incident reporting procedure immediately',
            'Notify the Privacy Office without delay',
            'Preserve evidence and avoid forwarding the data',
        ],
        'articles': ['KB2005'],
    },
]

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
        "1. Identify the affected product area (portal, claims, enrollment, provider)\n"
        "2. Decide whether it is access, data, or functionality\n"
        "3. Set priority by impact: single user is usually Medium, "
        "multiple users is High, and safety or security impact is Critical"
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
    lowered = message.lower()

    for phrase, text in GUIDANCE.items():
        if phrase in lowered:
            return AIResponse(reply=text)

    for entry in KNOWLEDGE:
        if any(keyword in lowered for keyword in entry['keywords']):
            reply = "Possible causes:\n"
            reply += "\n".join(f"- {c}" for c in entry['causes'])
            reply += "\n\nRecommended steps:\n"
            reply += "\n".join(f"{i}. {s}" for i, s in enumerate(entry['steps'], 1))
            if entry['articles']:
                reply += "\n\nRelated articles: " + ", ".join(entry['articles'])

            return AIResponse(
                reply=reply,
                suggested_category=entry['category'],
                suggested_priority=entry['priority'],
                suggested_request_type=entry['request_type'],
                related_articles=entry['articles'],
                similar_cases=[
                    {
                        'number': t['number'],
                        'url': t.get('url') or f"{SALESFORCE_CASE_BASE_URL}/{t['id']}/view",
                        'label': t.get('label', ''),
                    }
                    for t in entry.get('tickets', [])
                ],
            )

    return AIResponse(
        reply=(
            "I don't have a specific match for that yet. Try describing the "
            "product area and the symptom — for example \"patient portal not "
            "loading\" or \"claim rejected for a member\".\n\n"
            "You can also ask what information you need before creating a case, "
            "how to classify an issue, or when to escalate."
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
- If the extracts only partly answer the question, say what they do cover \
and state plainly what is missing.
- Prefer the exact wording of the extracts over your own phrasing when \
describing a procedure.

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


def _chips_from_results(results):
    """Derive article and case chips from what retrieval actually returned.

    Article codes come from chunk metadata; tickets are looked up from the
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
        a.code: a for a in KnowledgeArticle.objects.filter(code__in=codes)
    }

    related_articles = [code for code in codes if code in articles]

    similar_cases = []
    seen = set()
    for code in related_articles:
        for ticket in (articles[code].related_tickets or []):
            number = ticket.get('number')
            if number and number not in seen:
                seen.add(number)
                similar_cases.append(ticket)

    return related_articles, similar_cases

# ----------------------------------------------------------------------
# UAIS engine (not yet implemented)
# ----------------------------------------------------------------------

def _uais_response(message, user=None):
    """Live response from UAIS, grounded in retrieved knowledge base chunks."""
    results = kb_index.search(message)
    grounded = kb_index.is_grounded(results)

    if not grounded:
        results = []
        if STRICT_GROUNDING:
            logger.info('No grounded match; strict mode, skipping the model')
            return AIResponse(reply=NOT_FOUND_REPLY, engine='uais')

    context = _build_context(results) if grounded else None

    try:
        raw = uais_client.call_llm(
            prompt=message,
            system=_build_system_prompt(context=context),
            json_mode=True,
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