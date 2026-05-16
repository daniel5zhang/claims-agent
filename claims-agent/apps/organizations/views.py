from django.contrib.auth import login, logout, authenticate
from django.shortcuts import redirect
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user:
        login(request, user)
        return JsonResponse({"ok": True, "username": user.username, "display_name": user.display_name})
    return JsonResponse({"ok": False, "error": "用户名或密码错误"}, status=401)


@api_view(["POST"])
def logout_view(request):
    logout(request)
    return JsonResponse({"ok": True})


@api_view(["GET"])
def me_view(request):
    if request.user.is_authenticated:
        return JsonResponse({"username": request.user.username, "display_name": request.user.display_name})
    return JsonResponse({"error": "not authenticated"}, status=401)
