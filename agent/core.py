"""
ChemAgent — AI 化学教学 Agent 核心

Think → Route → Execute 循环
支持流式/非流式，多 Persona 切换
"""
import json
import os
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import yaml

from .memory import MemoryStack
from .skill_registry import registry
from .provider.base import ChatResult


@dataclass
class AgentConfig:
    persona: str = "tutor"  # tutor / teacher / parent
    provider: str = "deepseek"  # deepseek (fast) / mimo (multimodal/search) / zhipu / dashscope
    model: str = ""  # 留空用默认
    max_turns: int = 5
    temperature: float = 0.7


@dataclass
class AgentResponse:
    action: str = "reply"
    content: str = ""
    skill_calls: list = field(default_factory=list)
    tokens_used: int = 0


class ChemAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.memory = MemoryStack()
        self._persona = self._load_persona(config.persona)
        self._provider = self._init_provider()

    def _load_persona(self, name: str) -> dict:
        """加载 Persona 配置"""
        persona_dir = os.path.join(os.path.dirname(__file__), "personas")
        path = os.path.join(persona_dir, f"{name}.yaml")
        if not os.path.exists(path):
            # 回退到 tutor
            path = os.path.join(persona_dir, "tutor.yaml")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _init_provider(self):
        """初始化 LLM Provider"""
        from .provider.mimo import MiMoProvider
        from .provider.deepseek import DeepSeekProvider
        from .provider.zhipu import ZhipuProvider
        from .provider.dashscope import DashScopeProvider

        providers = {
            "mimo": MiMoProvider,
            "deepseek": DeepSeekProvider,
            "zhipu": ZhipuProvider,
            "dashscope": DashScopeProvider,
        }
        cls = providers.get(self.config.provider, DeepSeekProvider)
        if self.config.model:
            return cls(model=self.config.model)
        return cls()

    def _build_system_prompt(self) -> str:
        """构建 system prompt，注入 tools 和 student profile"""
        prompt = self._persona.get("system_prompt", "")

        # 注入可用工具列表
        tools_desc = ""
        for skill_name, skill in registry._skills.items():
            params = ", ".join(skill["parameters"].keys())
            tools_desc += f"\n  - **{skill_name}**: {skill['description']} (参数: {params})"
        prompt = prompt.replace("{tools}", tools_desc)

        # 注入学生画像
        profile = json.dumps(self.memory.student_profile, ensure_ascii=False)
        prompt = prompt.replace("{student_profile}", profile or "暂无学生信息")

        return prompt

    async def _think(self, messages: list[dict]) -> dict:
        """Think 阶段：LLM 决定下一步"""
        tools = registry.to_openai_tools() if registry._skills else None

        result = await self._provider.chat(
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=8192,
            tools=tools,
        )

        # 解析 LLM 响应
        content = result.content

        # 尝试提取 JSON
        decision = self._parse_decision(content, result.tool_calls)

        return {
            "decision": decision,
            "raw_content": content,
            "usage": result.usage,
        }

    def _parse_decision(self, content: str, tool_calls: list) -> dict:
        """解析 LLM 的决策（JSON 或 tool_calls）"""
        # 优先用原生 tool_calls
        if tool_calls:
            tc = tool_calls[0]
            func = tc.get("function", {})
            return {
                "action": "use_skill",
                "skill": func.get("name", ""),
                "args": json.loads(func.get("arguments", "{}")),
            }

        # 尝试从 content 中提取 JSON action（处理嵌套大括号）
        try:
            # 先去掉 markdown 代码块
            clean_content = content
            for fence in ("```json", "```"):
                if fence in clean_content:
                    clean_content = clean_content.split(fence)[1] if len(clean_content.split(fence)) > 1 else clean_content
            # 匹配嵌套大括号
            start = clean_content.find("{")
            if start >= 0:
                depth = 0
                end = start
                for i in range(start, len(clean_content)):
                    if clean_content[i] == "{": depth += 1
                    elif clean_content[i] == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end > start:
                    json_str = clean_content[start:end]
                    data = json.loads(json_str)
                    if "action" in data:
                        # Strip the JSON block from content for clean display
                        before = content[:content.find(json_str[:20])] if json_str[:20] in content else ""
                        after = content[content.find(json_str[:20])+len(json_str):] if json_str[:20] in content else ""
                        clean = (before + after).strip()
                        data["content"] = clean or data.get("content", "")
                        return data
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

        # fallback: 当作直接回复
        return {"action": "reply", "content": content}

    async def run(
        self, user_input: str, history: list[dict] = None
    ) -> AgentResponse:
        """非流式执行 Agent"""
        # 加载历史
        if history:
            for turn in history:
                self.memory.add_turn(turn.get("role", "user"), turn.get("content", ""))

        total_tokens = 0
        skill_calls = []

        for turn in range(self.config.max_turns):
            # 构建上下文
            system_prompt = self._build_system_prompt()
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self.memory.build_context(user_input))

            # Think
            think_result = await self._think(messages)
            total_tokens += think_result.get("usage", {}).get("total_tokens", 0)

            decision = think_result["decision"]

            if decision["action"] == "use_skill":
                # Execute skill
                skill_name = decision.get("skill", "")
                skill_args = decision.get("args", {})
                skill_result = await registry.execute(skill_name, skill_args)
                skill_calls.append(skill_name)

                # Observe: 把 skill 结果喂给 LLM
                observation = f"工具 {skill_name} 返回结果:\n{json.dumps(skill_result, ensure_ascii=False)}"
                self.memory.add_turn("user", user_input)
                self.memory.add_turn("assistant", observation)

                # 让 LLM 基于 skill 结果生成最终回复
                final_messages = [{"role": "system", "content": system_prompt}]
                final_messages.extend(self.memory.build_context("请基于以上工具结果生成回复"))

                final_result = await self._provider.chat(
                    messages=final_messages,
                    temperature=self.config.temperature,
                    max_tokens=8192,
                )
                total_tokens += final_result.usage.get("total_tokens", 0)

                self.memory.add_turn("assistant", final_result.content)
                return AgentResponse(
                    action="use_skill",
                    content=final_result.content,
                    skill_calls=skill_calls,
                    tokens_used=total_tokens,
                )

            else:
                # 直接回复
                self.memory.add_turn("user", user_input)
                self.memory.add_turn("assistant", decision.get("content", ""))
                return AgentResponse(
                    action="reply",
                    content=decision.get("content", ""),
                    skill_calls=skill_calls,
                    tokens_used=total_tokens,
                )

        # 超过 max_turns
        return AgentResponse(
            action="reply",
            content="抱歉，这个问题比较复杂。请换个方式提问，我会更好地帮助您。",
            tokens_used=total_tokens,
        )

    async def run_stream(
        self, user_input: str, history: list[dict] = None
    ) -> AsyncIterator[str]:
        """流式执行 Agent，输出结构化 SSE 事件"""
        if history:
            for turn in history:
                self.memory.add_turn(turn.get("role", "user"), turn.get("content", ""))

        system_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.memory.build_context(user_input))

        # Intent recognition + model routing
        def _classify(msg: str):
            """Return (provider_override, tools_list). provider_override=None means use default."""
            all_tools = registry.to_openai_tools() if registry._skills else []
            by_name = {t["function"]["name"]: t for t in all_tools}
            # Multimodal / web search → MiMo (slow)
            # Search: use DeepSeek for fast thinking, MiMo only for web_search execution
            if any(kw in msg for kw in ["搜", "查", "找", "真题", "高考", "图片", "照片", "图像", "识别", "OCR", "上传"]):
                return ("deepseek", [by_name[n] for n in ["search_exam_bank", "web_search"] if n in by_name])
            # Generate → DeepSeek (fast) with generate tools
            if any(kw in msg for kw in ["出题", "生成", "练习", "组卷", "题目"]):
                return ("deepseek", [by_name[n] for n in ["generate_questions", "search_exam_bank"] if n in by_name])
            # Diagnosis → DeepSeek (fast) with diagnosis tools
            if any(kw in msg for kw in ["诊断", "学生", "学情", "班级", "薄弱"]):
                return ("deepseek", [by_name[n] for n in ["diagnose_barrier", "search_exam_bank"] if n in by_name])
            # Chat → DeepSeek (fast), no tools
            return ("deepseek", None)

        provider_override, tools = _classify(user_input) if registry._skills else (None, None)
        if provider_override and provider_override != self.config.provider:
            # Switch provider on-the-fly for this request
            if provider_override == "deepseek":
                from .provider.deepseek import DeepSeekProvider
                self._provider = DeepSeekProvider(model="deepseek-chat")
            elif provider_override == "mimo":
                from .provider.mimo import MiMoProvider
                self._provider = MiMoProvider()

        # Phase 1: Thinking
        yield self._sse_event("phase", {"phase": "thinking"})

        think_result = await self._provider.chat(
            messages=messages,
            temperature=self.config.temperature,
            tools=tools,
        )

        # Parse decision: native tool_calls first, then JSON from content
        decision = self._parse_decision(think_result.content, think_result.tool_calls)
        if decision.get("action") == "use_skill":
            skill_name = decision["skill"]
            skill_args = decision.get("args", {})

            tool_category = skill_name.split("_")[0] if "_" in skill_name else skill_name
            yield self._sse_event("tool_call", {
                "name": skill_name,
                "tool": tool_category,
                "args": skill_args,
            })
            yield self._sse_event("phase", {"phase": "executing"})
            # Execute skill
            try:
                skill_result = await registry.execute(skill_name, skill_args)
                yield self._sse_event("tool_result", {
                    "name": skill_name,
                    "tool": tool_category,
                    "success": "error" not in skill_result,
                    "result": skill_result,
                })
            except Exception as e:
                yield self._sse_event("tool_error", {
                    "name": skill_name,
                    "tool": tool_category,
                    "error": str(e),
                })
                yield self._sse_event("done", {})
                return

            # Auto-retry: if search_exam_bank returns 0, try web_search
            if skill_name == "search_exam_bank" and skill_result.get("total", 0) == 0 and "web_search" in registry.list_skills():
                yield self._sse_event("phase", {"phase": "thinking"})
                try:
                    web_q = user_input  # 直接用用户的原始问题搜索，不加"高考化学真题"
                    web_result = await registry.execute("web_search", {"query": web_q})
                    yield self._sse_event("tool_call", {"name": "web_search", "tool": "web", "args": {"query": web_q}})
                    yield self._sse_event("phase", {"phase": "executing"})
                    yield self._sse_event("tool_result", {"name": "web_search", "tool": "web", "success": True, "result": web_result})
                    observation = f"search_exam_bank 无结果。web_search 返回:\n{web_result.get('result', '')[:3000]}"
                except Exception as e:
                    observation = f"search_exam_bank 无结果，web_search 也失败: {e}"
            else:
                observation = f"工具 {skill_name} 返回结果:\n{json.dumps(skill_result, ensure_ascii=False)}"
            self.memory.add_turn("user", user_input)
            self.memory.add_turn("assistant", observation)

            # Reply phase: clean prompt, no JSON format
            reply_sp = "你是高中化学教研助手。下面是工具执行结果和用户问题。请用自然语言回复。直接写回复内容，不要JSON。不要markdown代码块。"
            final_messages = [{"role": "system", "content": reply_sp}]
            final_messages.extend(self.memory.build_context(""))

            yield self._sse_event("phase", {"phase": "reply"})

            async for chunk in self._provider.chat_stream(
                messages=final_messages,
                temperature=self.config.temperature,
                max_tokens=8192,
            ):
                delta = self._extract_delta(chunk)
                if delta:
                    yield self._sse_event("text", {"content": delta})
        else:
            # Direct reply — 使用已解析的干净内容
            clean_text = decision.get("content", "")
            if clean_text:
                yield self._sse_event("phase", {"phase": "reply"})
                yield self._sse_event("text", {"content": clean_text})
                yield self._sse_event("done", {})
                return

            # 空回复时再调用流式
            self.memory.add_turn("user", user_input)
            reply_prompt = "你是高中化学教研助手。请用自然有帮助的方式直接回答。"
            reply_messages = [{"role": "system", "content": reply_prompt}]
            reply_messages.extend(self.memory.build_context(""))

            yield self._sse_event("phase", {"phase": "reply"})

            reply_full = ""
            async for chunk in self._provider.chat_stream(
                messages=reply_messages,
                temperature=self.config.temperature,
                max_tokens=8192,
            ):
                delta = self._extract_delta(chunk)
                if delta:
                    reply_full += delta
                    yield self._sse_event("text", {"content": delta})

            self.memory.add_turn("assistant", reply_full)

        # Done
        yield self._sse_event("done", {})

    def _sse_event(self, event_type: str, data: dict) -> str:
        """格式化 SSE 事件"""
        return json.dumps({"type": event_type, **data}, ensure_ascii=False)

    def _parse_direct_reply(self, content: str) -> str:
        """从 LLM 的 JSON 决策中提取纯文本回复"""
        try:
            import re
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                data = json.loads(match.group())
                if data.get("action") == "reply":
                    return data.get("content", content)
        except (json.JSONDecodeError, KeyError):
            pass
        return content  # 解析失败则返回原始文本

    def _extract_delta(self, chunk: str) -> str:
        """从 SSE chunk 提取文本增量"""
        try:
            if chunk.startswith("data: "):
                chunk = chunk[6:]
            if chunk == "[DONE]":
                return ""
            data = json.loads(chunk)
            choices = data.get("choices", [{}])
            delta = choices[0].get("delta", {}) or choices[0].get("message", {})
            return delta.get("content", "")
        except (json.JSONDecodeError, KeyError, IndexError):
            return ""

    async def close(self):
        if hasattr(self._provider, "close"):
            await self._provider.close()
