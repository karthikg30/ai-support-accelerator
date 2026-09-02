"""
Turns a conversation into starting values for a new case.

MVP: assembles the agent's own messages into a draft description and
carries the most recent classification suggestions.

TODO(uais): replace `_seed_mock` with a summarisation call once UAIS is
available — the model should produce a concise subject line and a
well-formed description from the whole exchange. The return shape must
stay the same so the view and template are unaffected.

Note: chat input is PHI-blocked before it is ever stored, so anything
seeded from a conversation has already passed the guardrail.
"""

from decouple import config

UAIS_ENABLED = config('UAIS_ENABLED', default=False, cast=bool)

MAX_SEED_DESCRIPTION = 3000


def seed_from_conversation(conversation):
    """Return a dict of initial form values for a new case."""
    if conversation is None:
        return {}

    messages = list(conversation.messages.order_by('created_at'))
    if not messages:
        return {}

    if UAIS_ENABLED:
        return _seed_uais(conversation, messages)
    return _seed_mock(conversation, messages)


def _seed_mock(conversation, messages):
    """Concatenate the agent's own turns; carry the latest suggestions."""
    lines = [m.message.strip() for m in messages if m.message.strip()]
    description = '\n'.join(lines)[:MAX_SEED_DESCRIPTION]

    subject = ''
    if lines:
        subject = lines[0][:200]

    category = ''
    request_type = ''
    priority = ''
    for m in reversed(messages):
        if not category and m.suggested_category:
            category = m.suggested_category
        if not request_type and m.suggested_request_type:
            request_type = m.suggested_request_type
        if not priority and m.suggested_priority:
            priority = m.suggested_priority
        if category and request_type and priority:
            break

    seed = {
        'subject': subject,
        'description': description,
    }
    if category:
        seed['product_category'] = category
    if request_type:
        seed['product_request_type'] = request_type
    if priority:
        seed['priority'] = priority

    return seed


def _seed_uais(conversation, messages):
    """Summarise the conversation into case fields — pending integration."""
    raise NotImplementedError(
        "UAIS conversation summarisation is not configured yet."
    )