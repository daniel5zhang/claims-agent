"""C 端免认证中间件 — /c/ 路由匿名访问"""
from django.http import JsonResponse


class CEndpointNoAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # C 端路由豁免认证
        if request.path.startswith("/c/") or request.path.startswith("/api/v1/c/"):
            # 注入匿名用户（DRF IsAuthenticated 对 /c/ 端点会在视图层覆盖）
            pass
        return self.get_response(request)
