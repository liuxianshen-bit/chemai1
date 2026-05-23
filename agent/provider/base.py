"""
LLM Provider 抽象接口

每个 Provider 实现: chat(非流式) + chat_stream(流式)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class ChatResult:
    """LLM 调用结果"""
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""
    finish_reason: str = ""


class LLMProvider(ABC):
    """LLM Provider 抽象基类。加新模型 = 实现这个接口。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[list[dict]] = None,
    ) -> ChatResult:
        """非流式调用"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[str]:
        """流式调用，yield SSE data chunks"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class ProviderError(Exception):
    """Provider 调用失败"""

    def __init__(self, message: str, status_code: int = 0, provider: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider
