import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ChatHistory, Conversation, PHIBlockEvent
from .services import phi_guard
from .services.ai_service import (
    MAX_MESSAGE_LENGTH,
    MAX_REPHRASE_LENGTH,
    PHIBlocked,
    get_ai_response,
    rephrase_text,
)

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

    try:
        result = get_ai_response(message, user=request.user)
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
    )

    conversation.set_title_from(message)
    conversation.save(update_fields=['updated_at'])

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

    history = Conversation.objects.filter(user=request.user)[:25]

    messages = []
    if conversation:
        messages = conversation.messages.order_by('created_at')

    return render(request, 'chatbot/assistant.html', {
        'conversation': conversation,
        'conversation_messages': messages,
        'history': history,
    })


@login_required
@require_POST
def new_conversation(request):
    return redirect('assistant')