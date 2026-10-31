"""
UAIS transport layer.

Authentication, token caching, and the HTTP call to the model. Knows
nothing about support cases, prompts or classification — those live in
ai_service.py.

PHI SAFETY: this module must never log prompt or response content.
Log status, latency and token counts only.
"""

import logging
import threading
import time

import httpx
import openai
from decouple import config

logger = logging.getLogger(__name__)

# --- authentication ---
AUTH_URL = config('UAIS_AUTH_URL', default='')
SCOPE = config('UAIS_SCOPE', default='')
GRANT_TYPE = config('UAIS_GRANT_TYPE', default='client_credentials')
CLIENT_ID = config('UAIS_CLIENT_ID', default='')
CLIENT_SECRET = config('UAIS_CLIENT_SECRET', default='')

# --- model ---
ENDPOINT = config('UAIS_ENDPOINT', default='')
API_VERSION = config('UAIS_API_VERSION', default='')
DEPLOYMENT = config('UAIS_DEPLOYMENT', default='')
PROJECT_ID = config('UAIS_PROJECT_ID', default='')
TIMEOUT = config('UAIS_TIMEOUT', default=30, cast=int)

TOKEN_SAFETY_MARGIN = 60          # refresh this many seconds before expiry


class UAISError(Exception):
    """Transport-level failure talking to UAIS."""


# ----------------------------------------------------------------------
# Token caching
# ----------------------------------------------------------------------

_token_lock = threading.Lock()
_token_value = None
_token_expires_at = 0.0


def _fetch_token():
    """One OAuth client-credentials round trip. Returns (token, expires_in)."""
    body = {
        'grant_type': GRANT_TYPE,
        'scope': SCOPE,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(AUTH_URL, headers=headers, data=body)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise UAISError(f'Authentication request failed: {exc}') from exc

    token = data.get('access_token')
    if not token:
        raise UAISError('Authentication response did not contain access_token')

    return token, int(data.get('expires_in', 3600))


def get_token():
    """Return a valid access token, fetching a new one only when needed."""
    global _token_value, _token_expires_at

    if _token_value and time.time() < _token_expires_at:
        return _token_value

    with _token_lock:
        # Re-check: another thread may have refreshed while we waited.
        now = time.time()
        if _token_value and now < _token_expires_at:
            return _token_value

        token, expires_in = _fetch_token()
        _token_value = token
        _token_expires_at = now + max(expires_in - TOKEN_SAFETY_MARGIN, 30)
        logger.info('UAIS token refreshed, valid for %ss', expires_in)
        return _token_value


# ----------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------

_client = None
_client_lock = threading.Lock()


def _get_client():
    """Module-level client. The token provider is called per request, so a
    single client instance stays valid across token refreshes."""
    global _client

    if _client is not None:
        return _client

    with _client_lock:
        if _client is None:
            _client = openai.AzureOpenAI(
                azure_endpoint=ENDPOINT,
                api_version=API_VERSION,
                azure_deployment=DEPLOYMENT,
                azure_ad_token_provider=get_token,
                default_headers={'projectId': PROJECT_ID},
                timeout=TIMEOUT,
                max_retries=2,
            )
    return _client


# ----------------------------------------------------------------------
# Public interface
# ----------------------------------------------------------------------

def call_llm(prompt, system=None, json_mode=False, temperature=0.2):
    """Send a prompt to UAIS and return the raw text response.

    json_mode requires the word "json" to appear somewhere in the prompt,
    or the API rejects the request. The caller's system prompt must
    include it.
    """
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})

    payload = {
        'model': DEPLOYMENT,
        'messages': messages,
        'temperature': temperature,
    }
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}

    client = _get_client()
    started = time.time()

    try:
        response = client.chat.completions.create(**payload)
    except Exception as exc:
        # Some corporate gateways reject the temperature parameter.
        if 'temperature' not in str(exc).lower():
            logger.error('UAIS call failed: %s', exc)
            raise UAISError(f'UAIS request failed: {exc}') from exc

        payload.pop('temperature', None)
        try:
            response = client.chat.completions.create(**payload)
        except Exception as retry_exc:
            logger.error('UAIS call failed after temperature retry: %s', retry_exc)
            raise UAISError(f'UAIS request failed: {retry_exc}') from retry_exc

    elapsed = time.time() - started

    if not response.choices:
        raise UAISError('UAIS returned no choices')

    usage = getattr(response, 'usage', None)
    logger.info(
        'UAIS ok in %.2fs, prompt_tokens=%s completion_tokens=%s',
        elapsed,
        getattr(usage, 'prompt_tokens', '?'),
        getattr(usage, 'completion_tokens', '?'),
    )

    return response.choices[0].message.content or ''