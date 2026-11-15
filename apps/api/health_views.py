from django.http import JsonResponse
from django.db import connection
from django.conf import settings
import httpx
import redis
import logging

logger = logging.getLogger(__name__)

def liveness_check(request):
    """Kubernetes/Load-balancer basic liveness probe."""
    return JsonResponse({"status": "healthy", "check": "liveness"}, status=200)

def readiness_check(request):
    """Readiness probe checking database connectivity."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ready", "database": "connected"}, status=200)
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        return JsonResponse({"status": "not_ready", "error": str(e)}, status=503)

def detailed_health_check(request):
    """Detailed system health check for DB, Redis, and Ollama."""
    health_status = {
        "status": "healthy",
        "components": {}
    }
    has_error = False

    # 1. Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status["components"]["database"] = {"status": "ok"}
    except Exception as e:
        has_error = True
        health_status["components"]["database"] = {"status": "error", "message": str(e)}

    # 2. Redis
    redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
    try:
        r = redis.from_url(redis_url, socket_timeout=1.0)
        r.ping()
        health_status["components"]["redis"] = {"status": "ok"}
    except Exception as e:
        # Note: Redis might be optional in pure local-sync mode
        health_status["components"]["redis"] = {"status": "degraded", "message": str(e)}

    # 3. Ollama
    ollama_url = settings.WEBSITE_INTEL.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                health_status["components"]["ollama"] = {"status": "ok", "models": resp.json().get("models", [])}
            else:
                health_status["components"]["ollama"] = {"status": "degraded", "code": resp.status_code}
    except Exception as e:
        health_status["components"]["ollama"] = {"status": "unavailable", "message": str(e)}

    status_code = 503 if has_error else 200
    if has_error:
        health_status["status"] = "degraded"

    return JsonResponse(health_status, status=status_code)
