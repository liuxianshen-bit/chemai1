"""DeepSeek Provider — 供 tools.py 中需要自己调 LLM 的 skill 使用"""
import os
import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ChatResult:
    content: str
    tool_calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""


class DeepSeekProvider:
    def __init__(self, model: str = "deepseek-chat"):
        import httpx

        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = "https://api.deepseek.com/beta"
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        )

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] = None,
    ) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for attempt in range(3):
            try:
                resp = await self._client.post("/chat/completions", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    return ChatResult(
                        content=choice["message"].get("content", ""),
                        tool_calls=choice["message"].get("tool_calls", []),
                        usage=data.get("usage", {}),
                        model=data.get("model", ""),
                    )
                elif resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise Exception(f"API error {resp.status_code}: {resp.text[:200]}")
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)

        return ChatResult(content="", usage={})

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    async def close(self):
        await self._client.aclose()

    @property
    def model_name(self) -> str:
        return f"deepseek/{self.model}"


# Module-level singleton for the intent classifier (shared connection pool)
classifier_provider: DeepSeekProvider | None = None


def get_classifier_provider() -> DeepSeekProvider:
    """Return or create the shared classifier provider singleton."""
    global classifier_provider
    if classifier_provider is None:
        classifier_provider = DeepSeekProvider()
    return classifier_provider
