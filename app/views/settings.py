
import json
import logging
from urllib.parse import urlparse
from zoneinfo import available_timezones

import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from app.models import UserProfile
from app.services import ai_service

from .helpers import json_error

logger = logging.getLogger(__name__)

_username_validator = UnicodeUsernameValidator()
_VALID_TIMEZONES = available_timezones()


def _safe_back_url(url):
    """Return url only if it's a same-site relative path that isn't the settings page."""
    if url and url.startswith('/') and not url.startswith('//') and 'user_settings' not in url:
        return url
    return None


@login_required
def user_settings(request):
    profile = request.user.profile

    if request.method == "POST":
        ai_chat_always_open = request.POST.get("ai_chat_always_open") == "on"
        tz = request.POST.get("timezone", profile.timezone)

        if tz not in _VALID_TIMEZONES:
            messages.error(request, "Invalid timezone selected.")
            tz = profile.timezone

        profile.ai_chat_always_open = ai_chat_always_open
        profile.timezone = tz
        profile.save(update_fields=["ai_chat_always_open", "timezone"])
    else:
        next_url = _safe_back_url(request.GET.get('next', ''))
        if next_url:
            request.session['settings_back_url'] = next_url

    back_url = request.session.get('settings_back_url') or reverse('dashboard')
    conn     = ai_service.connection_for(profile)
    default  = ai_service.default_connection()

    return render(request, "user_settings.html", {
        "profile":       profile,
        "back_url":      back_url,
        "ai_provider":   ai_service.provider_name(conn),
        "ai_base_url":   conn.base_url,
        "ai_model_name": ai_service.model_display_name(profile.ai_model, conn),
        # Read by settings.js; the saved API key itself never goes to the browser.
        "ai_connection": {
            "provider":       profile.ai_provider,
            "base_url":       profile.ai_base_url,
            "key_hint":       profile.ai_api_key[-4:] if profile.ai_api_key else "",
            "default_name":   ai_service.provider_name(default),
            "default_url":    default.base_url,
            "server_key":     bool(settings.OPENROUTER_API_KEY),
            "preset_urls":    {p: ai_service.preset_url(p) for p in ("ollama", "lmstudio")},
        },
    })


@login_required
@require_POST
def edit_username(request):
    new_username = request.POST.get('username', '').strip()

    if not new_username:
        messages.error(request, "Username cannot be empty.")
        return redirect('user_settings')

    if len(new_username) > 150:
        messages.error(request, "Username must be 150 characters or fewer.")
        return redirect('user_settings')

    try:
        _username_validator(new_username)
    except ValidationError as e:
        messages.error(request, e.message)
        return redirect('user_settings')

    if User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
        messages.error(request, "That username is already taken.")
        return redirect('user_settings')

    request.user.username = new_username
    request.user.save(update_fields=['username'])
    messages.success(request, "Username updated successfully.")
    return redirect('user_settings')


@login_required
@require_POST
def edit_password(request):
    current_password = request.POST.get('current_password', '')
    new_password     = request.POST.get('new_password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not request.user.check_password(current_password):
        return json_error('Current password is incorrect.')

    if new_password != confirm_password:
        return json_error('New passwords do not match.')

    try:
        validate_password(new_password, request.user)
    except ValidationError as e:
        return json_error(' '.join(e.messages))

    request.user.set_password(new_password)
    request.user.save(update_fields=['password'])

    update_session_auth_hash(request, request.user)
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def edit_theme(request):
    theme = request.POST.get('theme', 'system')
    if theme not in ('light', 'dark', 'system'):
        theme = 'system'

    profile = request.user.profile
    profile.theme = theme
    profile.save(update_fields=['theme'])
    return redirect('user_settings')


@login_required
@require_POST
def save_ai_model(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return json_error('Invalid JSON.')

    model_id = data.get('model_id', '').strip()
    if not model_id:
        return json_error('Model ID cannot be empty.')
    if len(model_id) > 150:
        return json_error('Invalid model ID.')

    try:
        profile          = request.user.profile
        profile.ai_model = model_id
        profile.save(update_fields=['ai_model'])
    except Exception:
        logger.exception("Error saving AI model for user %s", request.user.pk)
        return json_error('An error occurred while saving your model selection.', 500)

    return JsonResponse({'status': 'success', 'model_id': model_id})


@login_required
def get_ai_models(request):
    conn = ai_service.connection_for(request.user.profile)
    try:
        models = ai_service.list_models(conn)
    except Exception:
        logger.warning("Failed to fetch model list from %s", conn.base_url, exc_info=True)
        return json_error(ai_service.unreachable_message(conn), 502)
    return JsonResponse({'status': 'success', 'models': models})


_AI_PROVIDERS = {value for value, _ in UserProfile.AI_PROVIDER_CHOICES}


def _connection_from_request(request):
    """(provider, base_url, api_key) from a JSON body; raises ValueError with a user message."""
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        raise ValueError('Invalid JSON.')

    provider = (data.get('provider') or '').strip()
    base_url = (data.get('base_url') or '').strip().rstrip('/')
    api_key  = (data.get('api_key') or '').strip()

    if provider not in _AI_PROVIDERS:
        raise ValueError('Unknown AI provider.')
    # Only Ollama, LM Studio and "Other" take a URL; only OpenRouter and "Other" take a key.
    if provider not in ('ollama', 'lmstudio', 'custom'):
        base_url = ''
    if provider not in ('openrouter', 'custom'):
        api_key = ''

    if provider == 'custom' and not base_url:
        raise ValueError('Enter the server URL.')
    if base_url:
        parsed = urlparse(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise ValueError('Server URL must start with http:// or https://')
        if len(base_url) > 200:
            raise ValueError('Server URL is too long.')
    if len(api_key) > 300:
        raise ValueError('API key is too long.')

    # A blank key keeps the saved one, but only for the same server, so a key
    # is never sent somewhere it wasn't entered for.
    profile = request.user.profile
    if not api_key and provider == profile.ai_provider and base_url == profile.ai_base_url:
        api_key = profile.ai_api_key

    return provider, base_url, api_key


@login_required
@require_POST
def save_ai_connection(request):
    try:
        provider, base_url, api_key = _connection_from_request(request)
    except ValueError as e:
        return json_error(str(e))

    profile = request.user.profile
    fields  = ['ai_provider', 'ai_base_url', 'ai_api_key']
    # A model picked for one server is rarely offered by another.
    if (provider, base_url) != (profile.ai_provider, profile.ai_base_url):
        profile.ai_model = None
        fields.append('ai_model')

    profile.ai_provider = provider
    profile.ai_base_url = base_url
    profile.ai_api_key  = api_key
    profile.save(update_fields=fields)
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def test_ai_connection(request):
    try:
        conn = ai_service.build_connection(*_connection_from_request(request))
    except ValueError as e:
        return json_error(str(e))

    name = ai_service.provider_name(conn)
    if ai_service.is_openrouter(conn) and not conn.api_key:
        return JsonResponse({'status': 'error', 'message': 'OpenRouter needs an API key.'})
    try:
        models = ai_service.list_models(conn, use_cache=False)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            return JsonResponse({'status': 'error', 'message': f'{name} rejected the API key.'})
        return JsonResponse({'status': 'error', 'message': f'{name} returned an error ({e}).'})
    except Exception:
        return JsonResponse({'status': 'error', 'message': f"Couldn't reach {name} at {conn.base_url}."})

    if not models:
        return JsonResponse({'status': 'error', 'message': f'Connected to {name}, but it has no models installed.'})
    return JsonResponse({'status': 'success', 'message': f'Connected to {name}: {len(models)} models available.'})
