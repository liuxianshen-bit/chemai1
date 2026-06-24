"""
Gateway — LLM-powered intent classifier replacing keyword matching.

Two-class classification (v2):
- chat: needs tool execution (tool decides routing via _route field)
- navigate: pure page open, no tool needed ("打开考试工作台")
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Page name → route mapping
PAGE_ROUTES = {
    "exam": "exam-v2",
    "exam-v2": "exam-v2",
    "diagnosis": "diagnosis",
    "students": "students",
    "teacher": "teacher",
    "chat": None,
}

CLASSIFY_PROMPT = """你是化学教研助手的意图分类器。回答两个问题：
1. 用户消息是否需要调用工具？
2. 如果不需要工具，目标页面是什么？

分类规则：
- **chat**: 需要调用工具完成任务（生成题目、诊断学情、查周报、搜索真题、答疑辅导、模拟实验、配平方程式、导入试卷等）。**不确定时一律走 chat**。
- **navigate**: 纯页面跳转，不需要任何工具（"打开考试工作台"、"去首页"、"查看班级列表"、"打开诊断页面"、"帮我打开学生管理"）。**只有明确说"打开/去/看看"某个页面的才走 navigate**。

返回 JSON（只返回 JSON，不要其他文字）：
{
  "type": "chat" | "navigate",
  "tools": [],
  "page": null | "exam-v2" | "diagnosis" | "students" | "teacher",
  "provider": "deepseek" | "mimo"
}

页面映射（仅 navigate 时需要）：
- "打开考试工作台" → exam-v2
- "打开诊断页面" → diagnosis
- "打开学生管理" → students
- "去首页/班级列表" → teacher
- 查询类（"有哪些学生""XX班的谁"）一律走 chat，不走 navigate

可用工具（仅 chat 时需要，最多3个，只从以下列表中选择）：
{tool_list}

Provider 选择：
- 图片/拍照/OCR/识别/上传 → mimo
- 其他 → deepseek

{conversation_context}
用户消息：{user_input}

JSON："""

# Full tool catalog with descriptions for prompt injection
_ALL_TOOL_DESCRIPTIONS = {
    "search_exam_bank": "搜索历年高考化学真题",
    "generate_questions": "AI生成化学题目",
    "diagnose_barrier": "诊断学生学习障碍类型",
    "web_search": "联网搜索最新化学资讯和高考动态",
    "balance_equation": "审核化学方程式配平",
    "chemistry_tutor": "引导式化学辅导答疑",
    "simulate_experiment": "模拟化学实验，生成实验报告",
    "weekly_report": "生成学生本周化学学习周报",
    "import_exam_paper": "从PDF导入试卷并审核入库",
    "assign_adaptive_practice": "根据学生障碍布置自适应练习",
}


def _build_tool_list(available_skills: list[str] | None) -> str:
    """Build the '可用工具' section for the classify prompt."""
    if not available_skills:
        skills = list(_ALL_TOOL_DESCRIPTIONS.keys())
    else:
        skills = available_skills

    lines = []
    for name in skills:
        desc = _ALL_TOOL_DESCRIPTIONS.get(name, "")
        if desc:
            lines.append(f"- {name}: {desc}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def _build_classify_prompt(
    user_input: str,
    available_skills: list[str] | None = None,
    conversation_context: str = "",
) -> str:
    """Build the full classification prompt with injected context."""
    tool_list = _build_tool_list(available_skills)
    ctx_block = f"对话历史：\n{conversation_context}" if conversation_context else ""
    return (
        CLASSIFY_PROMPT.replace("{tool_list}", tool_list)
        .replace("{conversation_context}", ctx_block)
        .replace("{user_input}", user_input)
    )


def _validate_tools(tools) -> list | None:
    """Validate and normalize the tools field from LLM output.

    Returns a list of tool name strings, or None if invalid.
    """
    if tools is None:
        return None
    if not isinstance(tools, list):
        logger.warning(
            "IntentClassifier: tools is not a list (got %s), falling back to None",
            type(tools).__name__,
        )
        return None
    result = [t for t in tools if isinstance(t, str)]
    if len(result) != len(tools):
        logger.warning(
            "IntentClassifier: %d non-string entries dropped from tools",
            len(tools) - len(result),
        )
    return result if result else None


@dataclass
class IntentResult:
    type: str = "chat"            # chat | navigate
    page: Optional[str] = None    # exam-v2 | diagnosis | students | teacher | None
    tools: Optional[list] = None  # None = all tools, [] = no tools
    provider: str = "deepseek"


class IntentClassifier:
    def __init__(self, provider):
        self._provider = provider

    async def classify(
        self,
        user_input: str,
        available_skills: list[str] | None = None,
        conversation_context: str = "",
    ) -> IntentResult:
        """LLM 语义分类 + tool 推荐。

        Args:
            user_input: 用户当前消息
            available_skills: 当前 persona 的可用 skill 名列表，None 表示全部
            conversation_context: 最近几轮对话历史（文本）
        """
        prompt = _build_classify_prompt(
            user_input,
            available_skills=available_skills,
            conversation_context=conversation_context,
        )

        try:
            result = await self._provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            return self._parse(result.content)
        except Exception:
            logger.warning("IntentClassifier: LLM call failed", exc_info=True)
            return self._keyword_fallback(user_input)

    def _parse(self, content: str) -> IntentResult:
        """Parse LLM JSON response with type validation and keyword fallback."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                raw_tools = data.get("tools", None)
                tools = _validate_tools(raw_tools)
                return IntentResult(
                    type=data.get("type", "chat"),
                    page=data.get("page"),
                    tools=tools,
                    provider=data.get("provider", "deepseek"),
                )
        except (json.JSONDecodeError, KeyError):
            logger.warning("IntentClassifier: JSON parse failed", exc_info=True)

        return self._keyword_fallback(content)

    def _keyword_fallback(self, text: str) -> IntentResult:
        """Keyword-based fallback when LLM parsing fails.

        Enhanced v2: now recommends specific tools instead of leaving tools=None.
        """
        provider = "deepseek"
        tools = None

        if any(kw in text for kw in ["图片", "照片", "图像", "识别", "OCR", "上传"]):
            provider = "mimo"

        # Pure page navigation (no tools) — only explicit open/go-to phrases
        if any(kw in text for kw in ["打开考试工作台", "打开学生管理", "打开诊断页面", "去首页"]):
            page = None
            if any(kw in text for kw in ["考试"]):
                page = "exam-v2"
            elif any(kw in text for kw in ["诊断"]):
                page = "diagnosis"
            elif any(kw in text for kw in ["学生管理"]):
                page = "students"
            elif any(kw in text for kw in ["首页"]):
                page = "teacher"
            if page:
                return IntentResult(type="navigate", page=page, tools=[], provider=provider)

        # Keyword-based tool recommendation
        tools = []
        if any(kw in text for kw in ["出题", "出", "生成", "练习", "组卷", "题目", "题", "考试", "组考"]):
            tools.append("generate_questions")
        if any(kw in text for kw in ["诊断", "学习障碍", "学情分析", "错题", "障碍"]):
            tools.append("diagnose_barrier")
        if any(kw in text for kw in ["周报", "学习报告", "本周"]):
            tools.append("weekly_report")
        if any(kw in text for kw in ["搜索", "真题", "高考"]):
            tools.append("search_exam_bank")
        if any(kw in text for kw in ["实验", "模拟"]):
            tools.append("simulate_experiment")
        if any(kw in text for kw in ["配平", "方程式"]):
            tools.append("balance_equation")
        if any(kw in text for kw in ["导入", "PDF", "试卷上传"]):
            tools.append("import_exam_paper")
        if any(kw in text for kw in ["自适应", "练习布置"]):
            tools.append("assign_adaptive_practice")

        if not tools:
            tools = None  # No keyword match → let Agent use all tools

        return IntentResult(type="chat", tools=tools, provider=provider)
