"""pydantic-ai Model 工厂 — 统一 4 个 LLM provider"""
import os
from dotenv import load_dotenv

load_dotenv()


def get_model(provider: str = "deepseek"):
    """根据 provider 名称返回 pydantic-ai Model。

    provider: deepseek | mimo | zhipu | dashscope
    """
    if provider == "deepseek":
        return "deepseek:deepseek-chat"

    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    if provider == "mimo":
        return OpenAIChatModel(
            "mimo-v2.5",
            provider=OpenAIProvider(
                base_url="https://api.xiaomimimo.com/v1",
                api_key=os.getenv("XIAOMI_API_KEY", ""),
            ),
        )

    if provider == "zhipu":
        return OpenAIChatModel(
            "GLM-4-Flash",
            provider=OpenAIProvider(
                base_url="https://open.bigmodel.cn/api/paas/v4",
                api_key=os.getenv("ZHIPU_API_KEY", ""),
            ),
        )

    if provider == "dashscope":
        return OpenAIChatModel(
            "qwen-turbo",
            provider=OpenAIProvider(
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            ),
        )

    raise ValueError(f"Unknown provider: {provider}")
