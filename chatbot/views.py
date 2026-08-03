import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import ChatHistory
from .services.ai_service import MAX_MESSAGE_LENGTH, get_ai_response


@login_required
@require_POST
def ask(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid request format.'}, status=400)

    message = (payload.get('message') or '').strip()
    source = payload.get('source', 'panel')

    if not message:
        return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {'error': f'Message is too long (limit {MAX_MESSAGE_LENGTH} characters).'},
            status=400,
        )

    if source not in ('panel', 'page'):
        source = 'panel'

    result = get_ai_response(message, user=request.user)

    ChatHistory.objects.create(
        user=request.user,
        message=message,
        response=result.reply,
        suggested_category=result.suggested_category,
        suggested_priority=result.suggested_priority,
        suggested_request_type=result.suggested_request_type,
        source=source,
        engine=result.engine,
    )

    return JsonResponse(result.to_dict())