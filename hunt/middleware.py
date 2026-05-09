from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


class SitePasswordMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        password = getattr(settings, "SITE_PASSWORD", "")
        if not password:
            return self.get_response(request)
        if self.is_allowed(request):
            return self.get_response(request)
        if self.wants_json(request):
            return JsonResponse({"error": "Voer eerst het site-wachtwoord in."}, status=403)
        return redirect(f"{reverse('site_login')}?next={request.get_full_path()}")

    def is_allowed(self, request):
        if request.path == reverse("site_login"):
            return True
        if request.path.startswith(settings.STATIC_URL):
            return True
        return request.session.get("site_unlocked") is True

    def wants_json(self, request):
        return (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.headers.get("Accept") == "application/json"
        )
