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

UAIS_ENABLED = config('UAIS_ENABLED', default=False, cast=bool)

MAX_MESSAGE_LENGTH = 2000


class AIResponse:
    """Uniform response shape, whether mock or live."""

    def __init__(self, reply, suggested_category='', suggested_priority='',
                 suggested_request_type='', related_articles=None, engine='mock'):
        self.reply = reply
        self.suggested_category = suggested_category
        self.suggested_priority = suggested_priority
        self.suggested_request_type = suggested_request_type
        self.related_articles = related_articles or []
        self.engine = engine

    def to_dict(self):
        return {
            'reply': self.reply,
            'suggested_category': self.suggested_category,
            'suggested_priority': self.suggested_priority,
            'suggested_request_type': self.suggested_request_type,
            'related_articles': self.related_articles,
        }


def get_ai_response(message, user=None):
    """Entry point used by views. Returns an AIResponse."""
    message = (message or '').strip()[:MAX_MESSAGE_LENGTH]

    if not message:
        return AIResponse(reply="Please type a question and I'll help.")

    if UAIS_ENABLED:
        return _uais_response(message, user)
    return _mock_response(message)


# ----------------------------------------------------------------------
# Mock engine
# ----------------------------------------------------------------------

KNOWLEDGE = [
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
        'articles': ['KB1020', 'KB1021'],
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
        'articles': ['KB1030'],
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
        'articles': ['KB1040'],
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
        'articles': ['KB1050', 'KB1051'],
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
        'articles': ['KB1060'],
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
# UAIS engine (not yet implemented)
# ----------------------------------------------------------------------

def _uais_response(message, user=None):
    raise NotImplementedError(
        "UAIS integration is not configured yet. Set UAIS_ENABLED=False "
        "to use the mock engine."
    )