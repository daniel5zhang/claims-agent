"""
用户身份识别中间件
从 X-User-ID 请求头获取用户标识，不存在则自动生成
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class UserIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = request.headers.get("X-User-ID", "")
        if not user_id:
            user_id = str(uuid.uuid4())
        request.state.user_id = user_id

        response: Response = await call_next(request)
        # 回传 user_id 给前端（应对自动生成的场景）
        response.headers["X-User-ID"] = user_id
        return response
