import logging
from django.core.cache import cache
from time import time
from django.http import JsonResponse

from .config import ALLOWED_FILE_TYPES, MAX_FILE_SIZE


logger = logging.getLogger(__name__)


class FileUploadMiddleware:
    """
    Middleware to protect the server from malicious and excessive large file uploads.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.FILES.get("file"):
            file = request.FILES.get("file")

            # Check file type
            if file.content_type not in ALLOWED_FILE_TYPES:
                return JsonResponse({"detail": "Unsupported file type."}, status=400)

            # Check file size
            if file.size > MAX_FILE_SIZE:
                return JsonResponse(
                    {
                        "detail": f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB."
                    },
                    status=400,
                )

        return self.get_response(request)


class RateLimitMiddleware:
    RATE_LIMIT = 20

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = self.get_client_ip(request)
        rate_limit_key = f"rate_limit:{ip}"
        request_times = cache.get(rate_limit_key, [])

        now = time()
        request_times = [t for t in request_times if now - t < 60]

        if len(request_times) >= self.RATE_LIMIT:
            logger.info(f"Rate limit exceeded for IP: {ip}.")
            return JsonResponse({"error": "Too many requests"}, status=429)

        # Add current request time and save to cache
        request_times.append(now)
        cache.set(rate_limit_key, request_times, timeout=60)

        logger.info(f"Request from IP: {ip}. Cache updated: {request_times}")

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
