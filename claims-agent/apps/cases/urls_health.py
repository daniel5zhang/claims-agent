from django.urls import path
from django.http import JsonResponse
from django.db import connections

def health(request):
    try:
        connections["default"].cursor().execute("SELECT 1")
        return JsonResponse({"status": "ok", "db": "ok"})
    except Exception as e:
        return JsonResponse({"status": "degraded", "db": "error", "detail": str(e)})

urlpatterns = [path("", health, name="health")]
