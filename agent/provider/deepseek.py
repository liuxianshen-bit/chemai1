"""
DeepSeek Provider — deepseek-v4-flash
纯文本主力：答疑/出题/诊断/报告/实验模拟
API: https://api.deepseek.com/v1/chat/completions
"""
import asyncio
import json
import os
from typing import AsyncIterator, Optional

import httpx

from .base import ChatResult, LLMProvider, ProviderError


class DeepSeekProvider(LLMProvider):
    def __init__(self, model: str = "deepseek-v4-flash", strict: bool = True):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        # Strict Mode 使用 /beta 端点
        self.base_url = "https://api.deepseek.com/beta" if strict else "https://api.deepseek.com/v1"
        self._model = model
        self._strict = strict
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def model_name(self) -> str:
        return f"deepseek/{self._model}"

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
                        f"DeepSeek {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                        provider="deepseek",
                    )
                    await asyncio.sleep(2**attempt)
                else:
                    raise ProviderError(
                        f"DeepSeek {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                        provider="deepseek",
                    )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = ProviderError(
                    str(e), provider="deepseek"
                )
                if attempt < 2:
                    await asyncio.sleep(1)

        raise last_error or ProviderError(
            "DeepSeek: max retries exceeded", provider="deepseek"
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
                            f"DeepSeek {resp.status_code}: {text[:200]}",
                            status_code=resp.status_code,
                            provider="deepseek",
                        )
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            yield line[6:]  # strip "data: " prefix
                return  # success, exit retry loop
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt == 2:
                    raise ProviderError(
                        str(e), provider="deepseek"
                    )
                await asyncio.sleep(1)

        raise ProviderError(
            "DeepSeek: max retries exceeded", provider="deepseek"
        )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
