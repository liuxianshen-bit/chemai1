"""MiMo 联网搜索 Skill"""
from agent.skill_registry import registry
import os, sys, json, asyncio, httpx


@registry.register(
    name="web_search",
    description="使用 MiMo 联网搜索功能查询实时信息。适用于需要最新化学资料、高考动态、教学资源等场景。",
    parameters={"query": "搜索查询内容"},
)
async def web_search(query: str = "") -> dict:
    api_key = os.getenv("XIAOMI_API_KEY", "")
    if not api_key:
        return {"error": "未配置 MiMo API Key"}

    payload = {
        "model": "mimo-v2.5",
        "messages": [{"role": "user", "content": query}],
        "enable_search": True,
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.xiaomimimo.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "query": query,
                "result": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {}),
            }
        return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:200]}
    except Exception as e:
        return {"error": str(e)}
