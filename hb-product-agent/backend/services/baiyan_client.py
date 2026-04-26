"""
阿里云百炼客户端封装
支持流式/非流式调用
"""
import json
import asyncio
from typing import AsyncIterator, Optional, Dict, Any, List
import httpx

from config import (
    BAILIAN_API_KEY,
    BAILIAN_APP_ID,
    BAILIAN_BASE_URL,
    LLM_MODEL,
    MULTIMODAL_MODELS,
)

DEFAULT_MODEL = LLM_MODEL

# 模块级 httpx 客户端复用（连接池），避免每次请求重新握手
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=120.0)
    return _http_client


class BaiyanClient:
    """阿里云百炼客户端"""

    def __init__(self, api_key: Optional[str] = None, app_id: Optional[str] = None):
        self.api_key = api_key or BAILIAN_API_KEY
        self.app_id = app_id or BAILIAN_APP_ID
        self.base_url = BAILIAN_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _is_multimodal(self, model: str) -> bool:
        """判断是否多模态模型"""
        return model in MULTIMODAL_MODELS or "vl" in model.lower()

    def _get_generation_url(self, model: str) -> str:
        """根据模型类型选择正确的 API 端点"""
        # 兼容 base_url 是否带有 /api/v1 后缀的两种情况
        base = self.base_url.rstrip("/")
        if base.endswith("/api/v1"):
            base = base[:-len("/api/v1")]
        elif base.endswith("/api"):
            base = base[:-len("/api")]

        if self._is_multimodal(model):
            return f"{base}/api/v1/services/aigc/multimodal-generation/generation"
        # 纯文本模型使用 OpenAI 兼容端点
        return f"{base}/compatible-mode/v1/chat/completions"

    def _build_payload(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream: bool,
        tools: Optional[List[Dict]],
        enable_thinking: bool,
    ) -> Dict[str, Any]:
        """构建 API 请求体，多模态用原生格式，文本模型用 OpenAI 兼容格式"""
        if self._is_multimodal(model):
            payload = {
                "model": model,
                "input": {"messages": messages},
                "parameters": {
                    "result_format": "message",
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "enable_thinking": enable_thinking,
                },
            }
            if stream:
                payload["parameters"]["incremental_output"] = True
        else:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if stream:
                payload["stream"] = True
            if enable_thinking:
                payload["enable_thinking"] = True

        if tools:
            payload["tools"] = tools
        return payload

    def extract_content(self, response: Dict[str, Any]) -> str:
        """从 API 响应中提取文本内容，兼容原生格式和 OpenAI 兼容格式"""
        # OpenAI 兼容格式：choices 在顶层
        if "choices" in response and response["choices"]:
            content = response["choices"][0].get("message", {}).get("content", "")
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                return "".join(text_parts)
            return content or ""
        # 原生 DashScope 格式：output.choices
        output = response.get("output", {})
        if "choices" in output and output["choices"]:
            content = output["choices"][0].get("message", {}).get("content", "")
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                return "".join(text_parts)
            return content or ""
        # 旧格式：output.text
        return output.get("text", "")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        enable_thinking: bool = False,
    ) -> Dict[str, Any]:
        """非流式对话 completion"""
        if not self.api_key:
            return self._mock_response(messages)

        payload = self._build_payload(
            model, messages, temperature, max_tokens, stream, tools, enable_thinking
        )

        url = self._get_generation_url(model)
        last_err = None
        for attempt in range(3):
            try:
                client = _get_http_client()
                resp = await client.post(url, headers=self.headers, json=payload)
                if resp.status_code == 200:
                    return resp.json()
                text = resp.text[:500]
                raise Exception(f"百炼 API 错误 {resp.status_code}: {text}")
            except Exception as e:
                last_err = e
                if attempt < 2:
                    await asyncio.sleep(1.5)
        raise last_err

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """流式对话 completion (SSE)"""
        if not self.api_key:
            yield self._mock_stream_content(messages)
            return

        payload = self._build_payload(
            model, messages, temperature, max_tokens, True, None, False
        )

        url = self._get_generation_url(model)
        client = _get_http_client()

        if self._is_multimodal(model):
            # 原生 SSE 格式：data: {...} 行，output.text 增量
            async with client.stream(
                "POST", url, headers=self.headers, json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get("output", {}).get("text", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        else:
            # OpenAI 兼容 SSE 格式
            async with client.stream(
                "POST", url, headers=self.headers, json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

    def _mock_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """无 API Key 时的 Mock 响应（OpenAI 兼容格式）"""
        last_msg = messages[-1].get("content", "") if messages else ""
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            f"[MOCK] 收到您的消息：{last_msg[:50]}...\n\n"
                            "（当前未配置阿里云百炼 API Key，此为模拟回复。"
                            "请在 .env 中配置 BAILIAN_API_KEY）"
                        ),
                        "role": "assistant",
                    },
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 0},
        }

    def _mock_stream_content(self, messages: List[Dict[str, str]]) -> str:
        last_msg = messages[-1].get("content", "") if messages else ""
        return f"[MOCK] 收到：{last_msg[:50]}...（未配置 API Key）"


# 全局客户端实例
_baiyan_client: Optional[BaiyanClient] = None


def get_baiyan_client() -> BaiyanClient:
    global _baiyan_client
    if _baiyan_client is None:
        _baiyan_client = BaiyanClient()
    return _baiyan_client
