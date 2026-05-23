"""
智谱 Provider — GLM-4.6V-FlashX (多模态) + GLM-4-Flash (文本)
API Key 与 OCR 服务共用 ZHIPU_API_KEY
API: https://open.bigmodel.cn/api/paas/v4/chat/completions
"""
import asyncio
import json
import os
from typing import AsyncIterator, Optional

import httpx

from .base import ChatResult, LLMProvider, ProviderError


class ZhipuProvider(LLMProvider):
    MODELS = {
        "vision": "GLM-4.6V-FlashX",   # 多模态（图片识别）
        "text": "GLM-4-Flash",         # 纯文本（备用）
    }

    def __init__(self, model: str = "vision"):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
        self._model_key = model
        self._model = self.MODELS.get(model, model)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def model_name(self) -> str:
        return f"zhipu/{self._model}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[list[dict]] = None,
    ) -> ChatResult:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        client = await self._get_client()
        last_error = None

        for attempt in range(3):
            try:
                resp = await client.post("/chat/completions", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    msg = choice.get("message", {})
                    return ChatResult(
                        content=msg.get("content", ""),
                        tool_calls=msg.get("tool_calls", []),
                        usage=data.get("usage", {}),
                        model=data.get("model", self._model),
                        finish_reason=choice.get("finish_reason", ""),
                    )
                elif resp.status_code == 429 or resp.status_code >= 500:
                    last_error = ProviderError(
                        f"Zhipu {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                        provider="zhipu",
                    )
                    await asyncio.sleep(2**attempt)
                else:
                    raise ProviderError(
                        f"Zhipu {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                        provider="zhipu",
                    )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = ProviderError(str(e), provider="zhipu")
                if attempt < 2:
                    await asyncio.sleep(1)

        raise last_error or ProviderError(
            "Zhipu: max retries exceeded", provider="zhipu"
        )

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        client = await self._get_client()

        for attempt in range(3):
            try:
                async with client.stream("POST", "/chat/completions", json=payload) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        if resp.status_code == 429 or resp.status_code >= 500:
                            await asyncio.sleep(2**attempt)
                            continue
                        raise ProviderError(
                            f"Zhipu {resp.status_code}: {text[:200]}",
                            status_code=resp.status_code,
                            provider="zhipu",
                        )
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            yield line[6:]
                return
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt == 2:
                    raise ProviderError(str(e), provider="zhipu")
                await asyncio.sleep(1)

        raise ProviderError(
            "Zhipu: max retries exceeded", provider="zhipu"
        )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
