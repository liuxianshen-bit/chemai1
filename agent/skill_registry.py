"""
Skill Registry — 装饰器注册 + OpenAI function calling 生成
"""
import asyncio
from typing import Any, Callable


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, dict] = {}
        self._provider = None  # 由 agent 注入，供需要 LLM 的 skill 复用

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, str],
    ):
        """装饰器：注册一个 Skill"""

        def decorator(func: Callable):
            self._skills[name] = {
                "name": name,
                "description": description,
                "parameters": parameters,
                "func": func,
            }
            return func

        return decorator

    async def execute(self, name: str, args: dict) -> dict:
        """执行指定 Skill（30s 超时保护）"""
        if name not in self._skills:
            return {"error": f"Skill '{name}' not found"}
        try:
            func = self._skills[name]["func"]
            return await asyncio.wait_for(func(**args), timeout=30)
        except asyncio.TimeoutError:
            return {"error": f"Skill '{name}' timed out after 30s"}
        except Exception as e:
            return {"error": f"Skill '{name}' failed: {str(e)}"}

    def set_provider(self, provider):
        """注入 LLM provider，供 skill 通过 registry._provider 获取"""
        self._provider = provider

    def to_openai_tools(self, strict: bool = True) -> list[dict]:
        """生成 OpenAI function calling 格式的 tool definitions。strict=True 时启用 DeepSeek Strict Mode。"""
        tools = []
        for skill in self._skills.values():
            properties = {}
            required = []
            for param_name, param_desc in skill["parameters"].items():
                properties[param_name] = {
                    "type": "string",
                    "description": param_desc,
                }
                required.append(param_name)

            func_def = {
                "name": skill["name"],
                "description": skill["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
            if strict:
                func_def["strict"] = True
                func_def["parameters"]["additionalProperties"] = False

            tools.append({"type": "function", "function": func_def})
        return tools

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def get_description(self, name: str) -> str:
        skill = self._skills.get(name)
        if not skill:
            return "Unknown skill"
        params = ", ".join(skill["parameters"].keys())
        return f"{skill['description']} (参数: {params})"


# 全局单例
registry = SkillRegistry()
