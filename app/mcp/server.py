"""
MCP Server - 基于FastMCP风格的MCP协议实现
将ChemAI核心功能暴露为MCP工具
"""

import json
import base64
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, Body
from pydantic import BaseModel

router = APIRouter(prefix="/api/mcp", tags=["MCP"])

# 工具注册表
_tools: Dict[str, Callable] = {}
_tool_schemas: Dict[str, Dict] = {}


def tool(name: str = None, description: str = None, parameters: Dict = None):
    """
    装饰器：注册MCP工具
    """
    def decorator(func: Callable):
        tool_name = name or func.__name__
        _tools[tool_name] = func
        _tool_schemas[tool_name] = {
            "name": tool_name,
            "description": description or func.__doc__ or "",
            "parameters": parameters or {}
        }
        return func
    return decorator


class MCPRequest(BaseModel):
    """MCP请求"""
    tool: str
    arguments: Dict[str, Any] = {}


class MCPResponse(BaseModel):
    """MCP响应"""
    success: bool
    result: Any = None
    error: Optional[str] = None


# ==================== MCP端点 ====================

@router.get("/tools")
async def list_tools():
    """列出所有可用的MCP工具"""
    return {
        "success": True,
        "tools": [
            {
                "name": name,
                "description": schema["description"],
                "parameters": schema["parameters"]
            }
            for name, schema in _tool_schemas.items()
        ]
    }


@router.post("/call")
async def call_tool(request: MCPRequest):
    """调用MCP工具"""
    tool_name = request.tool
    arguments = request.arguments

    if tool_name not in _tools:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    try:
        result = await _tools[tool_name](**arguments)
        return MCPResponse(success=True, result=result)
    except Exception as e:
        return MCPResponse(success=False, error=str(e))


@router.post("/tools/{tool_name}")
async def call_tool_by_name(
    tool_name: str,
    arguments: Dict[str, Any] = Body(default={})
):
    """直接调用指定工具"""
    if tool_name not in _tools:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    try:
        result = await _tools[tool_name](**arguments)
        return MCPResponse(success=True, result=result)
    except Exception as e:
        return MCPResponse(success=False, error=str(e))


# ==================== 工具实现 ====================

@tool(name="ocr_recognize", description="识别试卷/答题卡/教材图片（百度教育OCR）")
async def ocr_recognize(image_data: str, paper_type: str = "auto") -> Dict:
    """
    识别图片中的答题内容

    Args:
        image_data: base64编码的图片数据
        paper_type: 纸张类型 (answer_sheet/printed/handwritten/mixed/auto)

    Returns:
        识别结果包含学生ID、答案、置信度等
    """
    from app.services.document_parse_service import get_document_parse_service

    try:
        file_data = base64.b64decode(image_data)
        service = get_document_parse_service()

        result = service.parse_document(
            file_data=file_data,
            file_type="image",
            source=paper_type if paper_type != "auto" else "auto"
        )

        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(name="generate_questions", description="根据知识点生成练习题")
async def generate_questions(
    knowledge_points: List[str],
    difficulty: str = "medium",
    quantity: int = 10,
    barrier_type: str = None,
    question_types: List[str] = None
) -> Dict:
    """
    生成练习题

    Args:
        knowledge_points: 知识点列表
        difficulty: 难度 (easy/medium/hard/competition)
        quantity: 题目数量
        barrier_type: 障碍类型 (concept/reading/expression)
        question_types: 题目类型 (choice/fill/calc)

    Returns:
        生成的题目列表
    """
    from app.services.llm_service import llm_service
    import time

    # 构建prompt
    barrier_prompts = {
        "concept": "重点考察学生对基础概念的深入理解，设置概念辨析类陷阱",
        "reading": "重点考察学生的审题能力，设置审题陷阱如偷换概念、遗漏关键信息",
        "expression": "重点考察学生的规范表述能力"
    }

    type_prompts = {
        "choice": "生成选择题，包含4个选项",
        "fill": "生成填空题",
        "calc": "生成计算题"
    }

    extra_instructions = []
    if barrier_type and barrier_type in barrier_prompts:
        extra_instructions.append(barrier_prompts[barrier_type])
    if question_types:
        type_hint = "、".join([type_prompts.get(t, t) for t in question_types])
        extra_instructions.append(f"题目类型: {type_hint}")

    difficulty_map = {"easy": "简单", "medium": "中等", "hard": "困难", "competition": "竞赛"}
    difficulty_hint = difficulty_map.get(difficulty, "中等")

    prompt = f"""请为以下知识点生成{quantity}道{difficulty_hint}难度的化学练习题:

知识点: {', '.join(knowledge_points)}
{' '.join(extra_instructions) if extra_instructions else ''}

请直接返回JSON，不要有其他文字:
{{
    "questions": [
        {{
            "content": "题目正文",
            "options": ["A. 选项", "B. 选项", "C. 选项", "D. 选项"],
            "answer": "正确答案",
            "knowledge_points": {knowledge_points},
            "difficulty": "{difficulty}"
        }}
    ]
}}"""

    result = llm_service.generate_text(
        prompt=prompt,
        system_prompt="你是一位资深高中化学教师，擅长生成高质量的化学练习题。",
        temperature=0.7
    )

    if result.get("success"):
        try:
            content = result["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            data = json.loads(content)
            return {"success": True, "questions": data.get("questions", [])}
        except json.JSONDecodeError:
            return {"success": False, "error": "LLM返回格式错误"}
    else:
        return {"success": False, "error": result.get("error", "LLM调用失败")}


@tool(name="generate_variant", description="根据原题生成变式练习")
async def generate_variant(
    original_question_id: str,
    quantity: int = 3
) -> Dict:
    """
    生成变式题

    Args:
        original_question_id: 原题ID
        quantity: 变式题数量

    Returns:
        生成的变式题列表
    """
    from app.services.wrong_question_trainer import generate_variant_questions

    variants = generate_variant_questions(original_question_id, quantity)

    if variants:
        return {"success": True, "variants": variants, "count": len(variants)}
    else:
        return {"success": False, "error": "变式题生成失败"}


@tool(name="get_wrong_questions", description="获取学生错题列表")
async def get_wrong_questions(
    student_id: str,
    limit: int = 20,
    knowledge_point: str = None
) -> Dict:
    """
    获取学生错题

    Args:
        student_id: 学生ID
        limit: 返回数量限制
        knowledge_point: 可选，按知识点筛选

    Returns:
        错题列表
    """
    from app.services.wrong_question_trainer import get_student_wrong_questions

    wrong_questions = get_student_wrong_questions(student_id, limit)
    # 按知识点筛选（如需要）
    if knowledge_point:
        wrong_questions = [q for q in wrong_questions if knowledge_point in q.get("knowledge_points", [])]

    return {
        "success": True,
        "student_id": student_id,
        "count": len(wrong_questions),
        "wrong_questions": wrong_questions
    }


@tool(name="create_training", description="创建错题强化训练会话")
async def create_training(
    student_id: str,
    question_ids: List[str]
) -> Dict:
    """
    创建强化训练会话

    Args:
        student_id: 学生ID
        question_ids: 题目ID列表

    Returns:
        训练会话信息
    """
    from app.services.wrong_question_trainer import create_training_session

    session = create_training_session(student_id, question_ids)

    return {"success": True, **session}


@tool(name="submit_training", description="提交训练结果")
async def submit_training(
    session_id: str,
    student_id: str,
    answers: List[Dict]
) -> Dict:
    """
    提交训练结果

    Args:
        session_id: 会话ID
        student_id: 学生ID
        answers: 答案列表 [{"question_id": "xxx", "answer": "A"}]

    Returns:
        训练结果
    """
    from app.services.wrong_question_trainer import submit_training_result

    result = submit_training_result(session_id, student_id, answers)

    return {"success": True, **result}


@tool(name="get_review_tasks", description="获取学生到期复习任务")
async def get_review_tasks(student_id: str) -> Dict:
    """
    获取复习任务

    Args:
        student_id: 学生ID

    Returns:
        复习任务列表
    """
    from app.services.spaced_repetition import get_due_review_tasks

    tasks = get_due_review_tasks(student_id)

    task_list = []
    for task in tasks:
        task_list.append({
            "task_id": task.task_id if hasattr(task, 'task_id') else str(task),
            "question_id": task.question_id if hasattr(task, 'question_id') else "",
            "review_level": task.review_level if hasattr(task, 'review_level') else 0,
            "status": task.status if hasattr(task, 'status') else "pending",
            "next_review_at": task.next_review_at.isoformat() if hasattr(task, 'next_review_at') and task.next_review_at else None
        })

    return {
        "success": True,
        "student_id": student_id,
        "count": len(task_list),
        "tasks": task_list
    }


@tool(name="complete_review", description="完成复习任务")
async def complete_review(
    task_id: str,
    is_correct: bool
) -> Dict:
    """
    完成复习

    Args:
        task_id: 复习任务ID
        is_correct: 是否答对

    Returns:
        更新后的任务状态
    """
    from app.services.spaced_repetition import complete_review

    result = complete_review(task_id, is_correct)

    if result:
        return {
            "success": True,
            "task_id": task_id,
            "review_level": result.review_level if hasattr(result, 'review_level') else 0,
            "status": result.status if hasattr(result, 'status') else "done"
        }
    else:
        return {"success": False, "error": "复习任务不存在"}


@tool(name="get_class_overview", description="获取班级学情概览")
async def get_class_overview(class_id: str) -> Dict:
    """
    获取班级概览

    Args:
        class_id: 班级ID

    Returns:
        班级学情数据
    """
    from app.services.data_visualization import DataVisualizationService
    from app.models.database import get_db

    db = next(get_db())
    try:
        service = DataVisualizationService(db)
        overview = service.get_class_overview(class_id)
        return {"success": True, **overview}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool(name="get_student_stats", description="获取学生学习统计")
async def get_student_stats(student_id: str) -> Dict:
    """
    获取学生统计

    Args:
        student_id: 学生ID

    Returns:
        学生学习数据
    """
    from app.services.data_visualization import DataVisualizationService
    from app.models.database import get_db

    db = next(get_db())
    try:
        service = DataVisualizationService(db)
        stats = service.get_student_personal_stats(student_id)
        return {"success": True, **stats}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool(name="trigger_warning_check", description="触发学情异常检测")
async def trigger_warning_check(class_id: str = None) -> Dict:
    """
    触发预警检测

    Args:
        class_id: 可选，指定班级ID

    Returns:
        检测到的预警列表
    """
    from app.services.early_warning import check_all_warnings

    warnings = check_all_warnings()

    return {
        "success": True,
        "count": len(warnings),
        "warnings": warnings
    }


@tool(name="get_pending_warnings", description="获取待处理预警列表")
async def get_pending_warnings(class_id: str = None) -> Dict:
    """
    获取预警列表

    Args:
        class_id: 班级ID（可选）

    Returns:
        待处理预警列表
    """
    from app.services.early_warning import get_pending_warnings as _get_pending

    warnings = _get_pending(class_id)

    return {
        "success": True,
        "class_id": class_id,
        "count": len(warnings),
        "warnings": warnings
    }


@tool(name="send_notification", description="发送通知")
async def send_notification(
    notification_type: str,
    title: str,
    content: str,
    target_type: str,
    target_ids: List[str] = None
) -> Dict:
    """
    发送通知

    Args:
        notification_type: 通知类型 (daily_report/weekly_report/score_alert/warning/reminder)
        title: 通知标题
        content: 通知内容
        target_type: 目标类型 (student/parent/teacher)
        target_ids: 目标ID列表

    Returns:
        发送结果
    """
    from app.services.notification_service import notification_service

    result = notification_service.send_notification(
        notification_type=notification_type,
        title=title,
        content=content,
        target_type=target_type,
        target_ids=target_ids
    )

    return result


@tool(name="diagnose_question", description="诊断题目障碍类型")
async def diagnose_question(
    question_content: str,
    student_answer: str = None,
    correct_answer: str = None
) -> Dict:
    """
    诊断题目障碍类型

    Args:
        question_content: 题目内容
        student_answer: 学生答案
        correct_answer: 正确答案

    Returns:
        诊断结果
    """
    from app.services.llm_service import llm_service

    result = llm_service.diagnose_barrier_type(
        student_error_history=[{
            "question": question_content,
            "wrong_answer": student_answer or "",
            "correct_answer": correct_answer or ""
        }],
        question_content=question_content,
        student_answer=student_answer,
        correct_answer=correct_answer
    )

    if result.get("success"):
        try:
            content = result["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            data = json.loads(content)
            return {"success": True, **data}
        except json.JSONDecodeError:
            return {"success": False, "error": "诊断结果解析失败"}
    else:
        return {"success": False, "error": result.get("error", "诊断失败")}


@tool(name="get_barrier_distribution", description="获取班级障碍类型分布")
async def get_barrier_distribution(class_id: str) -> Dict:
    """
    获取障碍分布

    Args:
        class_id: 班级ID

    Returns:
        障碍类型分布数据
    """
    from app.services.data_visualization import DataVisualizationService
    from app.models.database import get_db

    db = next(get_db())
    try:
        service = DataVisualizationService(db)
        distribution = service.get_barrier_distribution(class_id)
        return {"success": True, **distribution}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool(name="get_knowledge_heatmap", description="获取知识点掌握热力图")
async def get_knowledge_heatmap(class_id: str) -> Dict:
    """
    获取热力图

    Args:
        class_id: 班级ID

    Returns:
        知识点热力图数据
    """
    from app.services.data_visualization import DataVisualizationService
    from app.models.database import get_db

    db = next(get_db())
    try:
        service = DataVisualizationService(db)
        heatmap = service.get_knowledge_heatmap(class_id)
        return {
            "success": True,
            "class_id": class_id,
            "count": len(heatmap),
            "heatmap": heatmap
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()
