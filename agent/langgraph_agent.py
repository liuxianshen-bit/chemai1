"""ChemAI LangGraph Agent — ReAct agent factory.

Replaces pydantic-ai Agent with LangGraph ReAct agent:
- LLM 自主决定 tool 调用顺序和次数 (not preset DAG)
- interrupt() 嵌入 request_approval tool
- Tool 集合固定 per persona YAML (保证 interrupt/resume 兼容)
"""
import json, os, logging
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool as lc_tool

logger = logging.getLogger(__name__)

# ── Tool approval enforcement ──
TOOL_APPROVAL_REQUIRED = {"assign_adaptive_practice", "import_exam_paper"}


def get_tools_for_persona(persona: str) -> list:
    """Load persona YAML, return LangChain @tool list (fixed set per persona)."""
    from agent.agents import load_persona
    from agent.tools import TOOLS

    cfg = load_persona(persona)
    available = set(cfg.get("available_skills", []))

    _tool_by_name = {t.__name__: t for t in TOOLS}

    tools = []
    for name, fn in _tool_by_name.items():
        if name in available:
            wrapped = lc_tool(fn)
            # Attach requires_approval metadata
            if name in TOOL_APPROVAL_REQUIRED:
                wrapped.metadata = {"requires_approval": True}
            tools.append(wrapped)

    # Always add request_approval
    tools.append(_make_request_approval_tool())

    logger.info(f"[LangGraph] {persona}: {len(tools)} tools registered "
                f"(persona: {len(tools)-1}, +request_approval)")
    return tools


def _make_request_approval_tool():
    """Create the request_approval tool with interrupt() inside."""

    @lc_tool
    async def request_approval(message: str, context: str = "") -> str:
        """向老师请求确认。生成内容后需要老师审核时调用。
        只在真正需要人为判断时调，不要每步都问。
        例如：出完题后请老师预览、导入试卷前确认来源、布置练习前确认班级。"""
        interrupt({
            "type": "approval",
            "message": message,
            "context": context,
        })
        return "approved"

    return request_approval


def get_langchain_model(provider: str) -> ChatOpenAI:
    """Create ChatOpenAI instance for the given provider."""
    api_keys = {
        "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
        "mimo": os.getenv("XIAOMI_API_KEY", ""),
        "zhipu": os.getenv("ZHIPU_API_KEY", ""),
        "dashscope": os.getenv("DASHSCOPE_API_KEY", ""),
    }
    configs = {
        "deepseek": {"model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"},
        "mimo": {"model": "mimo-v2.5", "base_url": "https://api.xiaomimimo.com/v1"},
        "zhipu": {"model": "GLM-4-Flash", "base_url": "https://open.bigmodel.cn/api/paas/v4"},
        "dashscope": {"model": "qwen-turbo", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    }
    cfg = configs.get(provider, configs["deepseek"])
    return ChatOpenAI(
        model=cfg["model"],
        api_key=api_keys.get(provider, ""),
        base_url=cfg["base_url"],
        temperature=0.3,
        max_tokens=4096,
    )


def build_persona_prompt(persona: str, student_profile: dict | None = None,
                         intent_hints: str = "") -> str:
    """Build system prompt from persona YAML + optional hints."""
    from agent.agents import load_persona

    cfg = load_persona(persona)
    prompt = cfg.get("system_prompt", "")

    # Replace {tools} placeholder (not needed, LangGraph handles tool binding)
    prompt = prompt.replace("{tools}", "")

    # Replace {student_profile}
    profile_str = "暂无学生信息"
    if student_profile:
        profile_str = json.dumps(student_profile, ensure_ascii=False)
    prompt = prompt.replace("{student_profile}", profile_str)

    # Append intent hints
    if intent_hints:
        prompt += f"\n\n## 工具推荐\n{intent_hints}\n以上是推荐工具，你可以使用它们，也可以根据需要使用其他工具。自己判断最合适的。"

    # Add guardrail instructions
    prompt += """
## 行为规则
1. 教学任务优先使用工具，不要空口回答
2. request_approval 只在真正需要老师确认时调（出完题预览、导入前确认、布置前确认班级）
3. 信息不足时先反问，不要猜参数
4. 闲聊或纯知识问答直接回复，不调工具
5. 出题前确认：知识点范围、数量、难度、给哪个班"""

    return prompt


def create_chemai_agent(persona: str = "tutor", provider: str = "deepseek",
                        student_profile: dict | None = None,
                        intent_hints: str = "") -> "CompiledGraph":
    """Create a ChemAI ReAct agent.

    Args:
        persona: tutor | teacher | parent
        provider: deepseek | mimo | zhipu | dashscope
        student_profile: student info dict for system prompt
        intent_hints: classifier recommendations injected into prompt

    Returns:
        Compiled LangGraph ReAct agent with MemorySaver checkpointer.
    """
    tools = get_tools_for_persona(persona)
    model = get_langchain_model(provider)
    prompt = build_persona_prompt(persona, student_profile, intent_hints)

    return create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        checkpointer=MemorySaver(),
    )
