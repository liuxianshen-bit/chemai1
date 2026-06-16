"""
Gateway — LLM-powered intent classifier replacing keyword matching.

Replaces core.py:246-261 inline _classify() with semantic intent detection.
Also extracts structured parameters from natural language.
"""
import json
from dataclasses import dataclass, field
from typing import Optional

# Page name → route mapping
PAGE_ROUTES = {
    "exam": "exam-v2",
    "exam-v2": "exam-v2",
    "diagnosis": "diagnosis",
    "students": "students",
    "teacher": "teacher",
    "chat": None,
}

CLASSIFY_PROMPT = """你是化学教研助手的意图分类器。分析用户消息，返回 JSON（只返回 JSON，不要其他文字）：

{
  "intent": "chat" | "page_action" | "hybrid",
  "page": null | "exam-v2" | "diagnosis" | "students" | "teacher",
  "params": {},
  "tools": [],
  "provider": "deepseek" | "mimo"
}

意图类型：
- chat: 纯答疑/聊天（"什么是氧化还原"、"模拟钠和水的实验"）
- page_action: 直接操作页面（"打开考试工作台"、"看看张三的诊断"）
- hybrid: 先执行 skill 再跳转（"给张三出5道盐类水解的题"、"准备期中考试"）

页面映射：
- 出题/考试/组卷/题目/导题 → exam-v2
- 诊断/障碍/学习计划 → diagnosis
- 学生/学员/班级成员 → students
- 学情/班级概览/成绩趋势 → teacher

参数提取（从用户消息中提取，不知道就空）：
- student_name: 学生姓名
- knowledge_points: 知识点（逗号分隔）
- difficulty: "easy"|"medium"|"hard"
- quantity: 出题数量（数字字符串）
- exam_scope: 考试范围
- class_name: 班级名称

工具选择（从全部可用工具中选相关的，最多3个）：
- search_exam_bank: 搜索历年真题
- generate_questions: AI生成题目
- diagnose_barrier: 诊断学习障碍
- web_search: 联网搜索
- balance_equation: 配平化学方程式
- chemistry_tutor: 辅导答疑
- simulate_experiment: 模拟化学实验
- weekly_report: 生成周报
- import_exam_paper: 导入试卷
- assign_adaptive_practice: 布置自适应练习

Provider 选择：
- 图片/拍照/OCR/识别/上传 → mimo
- 其他 → deepseek

用户消息: {user_input}

JSON:"""


@dataclass
class IntentResult:
    intent: str = "chat"         # chat | page_action | hybrid
    page: Optional[str] = None   # exam-v2 | diagnosis | students | teacher | None
    params: dict = field(default_factory=dict)
    tools: Optional[list] = None  # None = all tools, [] = no tools
    provider: str = "deepseek"


class IntentClassifier:
    def __init__(self, provider):
        self._provider = provider

    async def classify(self, user_input: str) -> IntentResult:
        """LLM 语义分类 + 参数提取"""
        prompt = CLASSIFY_PROMPT.replace("{user_input}", user_input)

        try:
            result = await self._provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            return self._parse(result.content)
        except Exception:
            return IntentResult()  # safe fallback: chat

    def _parse(self, content: str) -> IntentResult:
        """Parse LLM JSON response with fallback to keyword matching."""
        # Try to extract JSON
        try:
            # Find JSON object in the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                return IntentResult(
                    intent=data.get("intent", "chat"),
                    page=data.get("page"),
                    params=data.get("params", {}),
                    tools=data.get("tools", None),
                    provider=data.get("provider", "deepseek"),
                )
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: keyword-based classification
        return self._keyword_fallback(content)

    def _keyword_fallback(self, text: str) -> IntentResult:
        """Keyword-based fallback when LLM parsing fails (kept from original _classify)."""
        all_tools = None  # None means "let the agent decide"
        provider = "deepseek"

        if any(kw in text for kw in ["图片", "照片", "图像", "识别", "OCR", "上传"]):
            provider = "mimo"

        if any(kw in text for kw in ["出题", "出", "生成", "练习", "组卷", "题目", "题", "考试", "组考"]):
            return IntentResult(intent="hybrid", page="exam-v2", tools=all_tools, provider=provider)
        if any(kw in text for kw in ["诊断", "学习计划"]):
            return IntentResult(intent="hybrid", page="diagnosis", tools=all_tools, provider=provider)
        if any(kw in text for kw in ["学生", "学员", "班级成员"]):
            return IntentResult(intent="page_action", page="students", tools=all_tools, provider=provider)
        if any(kw in text for kw in ["学情", "班级概览", "成绩趋势", "面板"]):
            return IntentResult(intent="page_action", page="teacher", tools=all_tools, provider=provider)

        return IntentResult(intent="chat", tools=all_tools, provider=provider)
