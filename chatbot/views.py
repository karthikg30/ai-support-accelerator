import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from decouple import config
from .models import ChatHistory, Conversation, PHIBlockEvent
from .services import phi_guard
from .services.ai_service import (
    MAX_MESSAGE_LENGTH,
    MAX_REPHRASE_LENGTH,
    SUMMARY_PREFIX,
    PHIBlocked,
    get_ai_response,
    rephrase_text,
    
)

HISTORY_DISPLAY_LIMIT = config('CHAT_HISTORY_DISPLAY', default=5, cast=int)
HISTORY_TURNS = config('CHAT_HISTORY_TURNS', default=4, cast=int)
HISTORY_REPLY_CHARS = config('CHAT_HISTORY_REPLY_CHARS', default=600, cast=int)


def _build_history(conversation):
    """Last N saved turns, oldest first, in the format ai_service expects."""
    rows = list(conversation.messages.order_by('-created_at')[:HISTORY_TURNS])[::-1]
    turns = []
    if conversation.summary:
        turns.append({
            'role': 'user',
            'content': SUMMARY_PREFIX + conversation.summary,
        })
        turns.append({'role': 'assistant', 'content': 'Understood.'})
    for r in rows:
        turns.append({'role': 'user', 'content': r.message or ''})
        turns.append({'role': 'assistant', 'content': (r.response or '')[:HISTORY_REPLY_CHARS]})
    return turns

import logging
import os

# Adjust this import to match how views.py already imports call_llm / UAISError.
from .services.uais_client import call_llm, UAISError

logger = logging.getLogger(__name__)

SUMMARY_WINDOW = HISTORY_TURNS   # turns kept verbatim; must match CHAT_HISTORY_TURNS (step 3)
SUMMARY_MAX_CHARS = int(os.environ.get('CHAT_SUMMARY_CHARS', 800))

SUMMARY_SYSTEM = (
    "Merge the EXISTING SUMMARY with the NEW TURNS into one updated summary. "
    "Record conversation state only, not KB procedure text, because that is "
    "retrieved fresh every turn. Keep: the product, whether the user is external "
    "or internal, the task, the step reached (for example 'Steps 1-2 of 7 done'), "
    "decisions or exceptions the user mentioned, the user's stated preferences "
    "(for example one step at a time), and open questions. "
    "Write in the third person. Drop greetings and repeated text. "
    "Plain text only, no bullets, no markdown. "
    f"Aim for about {SUMMARY_MAX_CHARS - 100} characters and never exceed {SUMMARY_MAX_CHARS}."
)


def _cap_at_sentence(text, limit):
    """Trim to limit, ending at a full sentence if possible, else a full word."""
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind('.')
    if end > limit * 0.5:
        return cut[:end + 1]
    return cut.rsplit(' ', 1)[0]


def _update_summary(conversation):
    """Fold turns that have fallen out of the history window into the summary.

    Never raises: if the LLM call fails, the chat reply is unaffected and
    the same turns are retried on the next message.
    """
    rows = list(
        ChatHistory.objects.filter(conversation=conversation).order_by('id')
    )
    if len(rows) <= SUMMARY_WINDOW:
        return

    already = conversation.summary_through or 0
    to_fold = [r for r in rows[:-SUMMARY_WINDOW] if r.id > already]
    if not to_fold:
        return

    turns_text = '\n\n'.join(
        f"User: {r.message}\nAssistant: {(r.response or '')[:600]}"
        for r in to_fold
    )
    prompt = (
        f"EXISTING SUMMARY:\n{conversation.summary or '(none)'}\n\n"
        f"NEW TURNS:\n{turns_text}\n\n"
        "Write the updated summary."
    )

    try:
        text = call_llm(prompt, system=SUMMARY_SYSTEM)
    except UAISError as exc:
        logger.warning('Summary update skipped: %s', exc)
        return

    conversation.summary = _cap_at_sentence(text, SUMMARY_MAX_CHARS)
    conversation.summary_through = to_fold[-1].id
    conversation.save(update_fields=['summary', 'summary_through'])


@login_required
@require_POST
def ask(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid request format.'}, status=400)

    message = (payload.get('message') or '').strip()
    source = payload.get('source', 'panel')
    conversation_id = payload.get('conversation_id')

    if not message:
        return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {'error': f'Message is too long (limit {MAX_MESSAGE_LENGTH} characters).'},
            status=400,
        )

    if source not in ('panel', 'page', 'assistant'):
        source = 'panel'

    # Resolve or start the thread — ownership enforced.
    conversation = None
    if conversation_id:
        conversation = Conversation.objects.filter(
            pk=conversation_id, user=request.user
        ).first()
    if conversation is None:
        conversation = Conversation.objects.create(user=request.user)

    # Previous turns of this conversation (read BEFORE saving the current one).
    history = _build_history(conversation)

    try:
        result = get_ai_response(
            message,
            user=request.user,
            history=history,
            active_product=conversation.active_product,
        )
    except PHIBlocked as blocked:
        PHIBlockEvent.objects.create(
            user=request.user,
            source=source,
            detected_types=', '.join(blocked.labels),
        )
        return JsonResponse({
            'error': (
                'This message appears to contain PHI '
                f'({phi_guard.describe(blocked.labels)}). '
                'The assistant cannot process patient information. '
                'Please remove it and describe the issue in general terms.'
            ),
            'conversation_id': conversation.pk,
        }, status=400)

    ChatHistory.objects.create(
        user=request.user,
        conversation=conversation,
        message=message,
        response=result.reply,
        suggested_category=result.suggested_category,
        suggested_priority=result.suggested_priority,
        suggested_request_type=result.suggested_request_type,
        source=source,
        engine=result.engine,
        related_articles=result.related_articles,
        similar_cases=result.similar_cases,
    )

    if result.product:
        conversation.active_product = result.product

    _update_summary(conversation)

    conversation.set_title_from(message)
    conversation.save(update_fields=['updated_at', 'active_product'])

    data = result.to_dict()
    data['conversation_id'] = conversation.pk
    return JsonResponse(data)


@login_required
@require_POST
def rephrase(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid request format.'}, status=400)

    text = (payload.get('text') or '').strip()

    if not text:
        return JsonResponse({'error': 'Nothing to rephrase.'}, status=400)

    if len(text) > MAX_REPHRASE_LENGTH:
        return JsonResponse(
            {'error': f'Text is too long (limit {MAX_REPHRASE_LENGTH} characters).'},
            status=400,
        )

    try:
        result = rephrase_text(text, user=request.user)
    except PHIBlocked as blocked:
        PHIBlockEvent.objects.create(
            user=request.user,
            source='rephrase',
            detected_types=', '.join(blocked.labels),
        )
        return JsonResponse({
            'error': (
                'The description appears to contain PHI '
                f'({phi_guard.describe(blocked.labels)}). '
                'Move patient information into the PHI Information field, '
                'then rephrase again.'
            )
        }, status=400)

    if not result.success:
        return JsonResponse({'error': result.error}, status=400)

    ChatHistory.objects.create(
        user=request.user,
        message=text,
        response=result.text,
        source='rephrase',
        engine=result.engine,
    )

    return JsonResponse(result.to_dict())


@login_required
def assistant(request):
    """AI-first landing page: chat with a conversation history rail."""
    conversation = None
    conversation_id = request.GET.get('c')

    if conversation_id:
        conversation = get_object_or_404(
            Conversation, pk=conversation_id, user=request.user
        )

    history = (
        Conversation.objects
        .filter(user=request.user)
        .order_by('-updated_at')[:HISTORY_DISPLAY_LIMIT]
    )

    messages = []
    if conversation:
        messages = conversation.messages.order_by('created_at')

    return render(request, 'chatbot/assistant.html', {
        'conversation': conversation,
        'conversation_messages': messages,
        'history': history,
        'history_limit': HISTORY_DISPLAY_LIMIT,
    })

@login_required
@require_POST
def new_conversation(request):
    return redirect('assistant')