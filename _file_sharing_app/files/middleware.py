from django.http import JsonResponse
from django.core.cache import cache
from time import time


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = self.get_client_ip(request)
        rate_limit_key = f"rate_limit:{ip}"
        request_times = cache.get(rate_limit_key, [])

        # Remove expired entries
        now = time()
        request_times = [t for t in request_times if now - t < 60]

        if len(request_times) >= 10:  # Limit to 10 requests per minute
            return JsonResponse({"error": "Too many requests"}, status=429)

        # Add current request time and save to cache
        request_times.append(now)
        cache.set(rate_limit_key, request_times, timeout=60)

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
