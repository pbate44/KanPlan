
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from app.forms import CustomUserCreationForm
from app.views.helpers import create_board_with_defaults

User = get_user_model()


def _safe_redirect_url(request, url, fallback="dashboard"):
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}):
        return url
    return fallback


def login_view(request):
    next_url = request.GET.get("next") or request.POST.get("next") or "dashboard"
    next_url = _safe_redirect_url(request, next_url)

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            remember_me = request.POST.get("remember") == "on"

            request.session.set_expiry(60 * 60 * 24 * 30 if remember_me else 0)

            login(request, user)
            return redirect(next_url)

    else:
        form = AuthenticationForm()

    return render(request, "login.html", {"form": form, "next": request.GET.get("next", "")})


def signup_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                create_board_with_defaults(user, "My First Board", "Getting started with KanPlan")

            login(request, user)
            messages.success(request, "Account created. Welcome!")
            return redirect("dashboard")
    else:
        form = CustomUserCreationForm()

    return render(request, "signup.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("login")


@login_required
@require_POST
def delete_account(request):
    confirm = request.POST.get("confirm_delete")
    user = request.user

    if not confirm:
        messages.error(request, "Please confirm account deletion.")
        return redirect("user_settings")

    password = request.POST.get("password", "")
    if not user.check_password(password):
        messages.error(request, "Incorrect password. Account was not deleted.")
        return redirect("user_settings")

    logout(request)
    user.delete()
    return redirect("goodbye")


def goodbye(request):
    return render(request, "account/goodbye.html")
