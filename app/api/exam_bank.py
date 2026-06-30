"""
F6: 历年真题库管理 API
支持手动选题和自定义真题集管理
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import (
    QuestionSet, QuestionSetItem, Question, HistoricalExam,
    get_db, Difficulty, QuestionSource, AuditStatus
)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class QuestionSetCreate(BaseModel):
    """创建真题集请求"""
    name: str
    teacher_id: Optional[str] = None
    region: Optional[str] = None
    year: Optional[int] = None
    source: Optional[str] = None
    description: Optional[str] = None


class QuestionSetResponse(BaseModel):
    """真题集响应"""
    set_id: str
    name: str
    region: Optional[str]
    year: Optional[int]
    source: Optional[str]
    description: Optional[str]
    question_count: int
    is_system: bool
    created_at: str


class QuestionFormatRequest(BaseModel):
    """题目格式化请求（OCR识别结果转标准题目）"""
    raw_text: str  # OCR识别的原始文本
    source_info: Optional[str] = None  # 来源信息


class QuestionFormatResponse(BaseModel):
    """题目格式化响应"""
    success: bool
    questions: List[Dict]  # 格式化后的题目列表
    message: str


class ImportQuestionsRequest(BaseModel):
    """导入题目到真题集请求"""
    set_id: str
    questions: List[Dict]  # 题目列表 [{content, options, answer, knowledge_points, difficulty}]


# ==================== 真题集管理 API ====================

@router.post("/exam-sets", response_model=Dict)
async def create_exam_set(request: QuestionSetCreate, db: Session = Depends(get_db)):
    """
    创建自定义真题集
    """
    try:
        set_id = f"qset_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        question_set = QuestionSet(
            set_id=set_id,
            name=request.name,
            teacher_id=request.teacher_id,
            region=request.region,
            year=request.year,
            source=request.source,
            description=request.description,
            question_count=0,
            is_system=False
        )
        db.add(question_set)
        db.commit()

        return {
            "success": True,
            "message": "真题集创建成功",
            "exam_set": {
                "set_id": set_id,
                "name": request.name,
                "region": request.region,
                "year": request.year,
                "source": request.source,
                "question_count": 0,
                "is_system": False,
                "created_at": datetime.now().isoformat()
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"创建失败: {str(e)}"}


@router.get("/exam-sets", response_model=Dict)
async def get_exam_sets(
    teacher_id: Optional[str] = None,
    region: Optional[str] = None,
    year: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """
    获取真题集列表
    支持按教师、地区、年份筛选
    """
    query = db.query(QuestionSet)

    if teacher_id:
        query = query.filter(QuestionSet.teacher_id == teacher_id)
    if region:
        query = query.filter(QuestionSet.region == region)
    if year:
        query = query.filter(QuestionSet.year == year)

    # 优先显示用户自定义真题集，其次系统真题集
    query = query.order_by(QuestionSet.is_system.asc(), QuestionSet.created_at.desc())

    total = query.count()
    sets = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "exam_sets": [
                {
                    "set_id": s.set_id,
                    "name": s.name,
                    "region": s.region,
                    "year": s.year,
                    "source": s.source,
                    "description": s.description,
                    "question_count": s.question_count,
                    "is_system": s.is_system,
                    "created_at": s.created_at.isoformat() if s.created_at else ""
                }
                for s in sets
            ]
        }
    }


@router.get("/exam-sets/{set_id}", response_model=Dict)
async def get_exam_set_detail(set_id: str, db: Session = Depends(get_db)):
    """
    获取真题集详情（包含所有题目）
    """
    question_set = db.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
    if not question_set:
        raise HTTPException(status_code=404, detail=f"真题集 {set_id} 不存在")

    # 查询真题集包含的题目
    items = db.query(QuestionSetItem).filter(
        QuestionSetItem.set_id == set_id
    ).order_by(QuestionSetItem.sort_order).all()

    questions = []
    for item in items:
        question = db.query(Question).filter(Question.question_id == item.question_id).first()
        if question:
            questions.append({
                "question_id": question.question_id,
                "content": question.content,
                "options": question.options,
                "answer": question.answer,
                "analysis": question.analysis,
                "knowledge_points": question.knowledge_points,
                "difficulty": question.difficulty.value if question.difficulty else "medium",
                "sort_order": item.sort_order
            })

    return {
        "success": True,
        "data": {
            "set_id": question_set.set_id,
            "name": question_set.name,
            "region": question_set.region,
            "year": question_set.year,
            "source": question_set.source,
            "description": question_set.description,
            "question_count": len(questions),
            "questions": questions,
            "created_at": question_set.created_at.isoformat() if question_set.created_at else ""
        }
    }


@router.delete("/exam-sets/{set_id}/questions/{question_id}", response_model=Dict)
async def remove_question_from_set(set_id: str, question_id: str, db: Session = Depends(get_db)):
    """从题库中移除单道题目"""
    question_set = db.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
    if not question_set:
        raise HTTPException(status_code=404, detail=f"题库 {set_id} 不存在")

    # 删除关联
    deleted = db.query(QuestionSetItem).filter(
        QuestionSetItem.set_id == set_id,
        QuestionSetItem.question_id == question_id
    ).delete()

    if deleted:
        # 更新题目计数
        question_set.question_count = db.query(QuestionSetItem).filter(
            QuestionSetItem.set_id == set_id
        ).count()
        db.commit()
        return {"success": True, "message": "题目已从题库移除"}
    else:
        return {"success": False, "message": "题库中未找到该题目"}


@router.delete("/exam-sets/{set_id}", response_model=Dict)
async def delete_exam_set(set_id: str, db: Session = Depends(get_db)):
    """
    删除真题集（只能删除用户自定义的）
    """
    question_set = db.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
    if not question_set:
        raise HTTPException(status_code=404, detail=f"真题集 {set_id} 不存在")

    if question_set.is_system:
        return {"success": False, "message": "系统预设真题集不能删除"}

    # 删除关联的题目（软删除，实际只是解除关联）
    db.query(QuestionSetItem).filter(QuestionSetItem.set_id == set_id).delete()

    # 删除真题集
    db.delete(question_set)
    db.commit()

    return {"success": True, "message": "真题集已删除"}


# ==================== 题目格式化 API ====================

@router.post("/format-questions", response_model=QuestionFormatResponse)
async def format_questions_from_text(request: QuestionFormatRequest, db: Session = Depends(get_db)):
    """
    将OCR识别的原始文本格式化为标准题目
    调用LLM进行格式化处理
    """
    try:
        from app.services.llm_service import llm_service

        system_prompt = """你是一位高中化学教研专家，负责将OCR识别的原始试卷文本格式化为标准的结构化题目。

要求：
1. 识别并提取每道题目，包括题号、正文、选项（如果有）、答案
2. 判断题目类型：选择题、填空题、解答题
3. 为每道题目标注知识点
4. 判断题目难度：easy/medium/hard
5. 保持题目原文，只做格式化和结构化，不修改内容

返回格式（JSON）：
{
    "questions": [
        {
            "type": "choice/fill/essay",
            "content": "题目正文",
            "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"],  // 选择题需要
            "answer": "正确答案",  // 简化的答案标识，如 "A" 或 "1"
            "knowledge_points": ["知识点1", "知识点2"],
            "difficulty": "easy/medium/hard"
        }
    ],
    "message": "处理说明"
}"""

        prompt = f"""请将以下OCR识别的试卷文本格式化为标准题目：

{request.raw_text}

{request.source_info if request.source_info else ''}

直接返回JSON，不要有其他文字。"""

        result = llm_service.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=4000
        )

        if result.get("success"):
            import json as json_lib
            content = result.get("content", "{}")

            # 清理可能的markdown代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            formatted_data = json_lib.loads(content.strip())

            return QuestionFormatResponse(
                success=True,
                questions=formatted_data.get("questions", []),
                message=formatted_data.get("message", "格式化完成")
            )
        else:
            return QuestionFormatResponse(
                success=False,
                questions=[],
                message=f"格式化失败: {result.get('error', '未知错误')}"
            )

    except Exception as e:
        return QuestionFormatResponse(
            success=False,
            questions=[],
            message=f"格式化异常: {str(e)}"
        )


# ==================== 导入题目 API ====================

@router.post("/import-questions", response_model=Dict)
async def import_questions_to_set(request: ImportQuestionsRequest, db: Session = Depends(get_db)):
    """
    导入题目到真题集
    """
    try:
        # 检查真题集是否存在
        question_set = db.query(QuestionSet).filter(QuestionSet.set_id == request.set_id).first()
        if not question_set:
            return {"success": False, "message": "真题集不存在"}

        imported_count = 0
        current_max_order = db.query(QuestionSetItem).filter(
            QuestionSetItem.set_id == request.set_id
        ).count()

        for i, q in enumerate(request.questions):
            # 检查题目是否已存在（根据内容hash去重）
            content_hash = str(hash(q.get("content", "")))[:16]
            existing = db.query(Question).filter(
                Question.content == q.get("content")
            ).first()

            if existing:
                question_id = existing.question_id
            else:
                # 创建新题目
                question_id = f"q_{datetime.now().strftime('%Y%m%d%H%M%S')}_{imported_count}"
                difficulty = Difficulty.MEDIUM
                if q.get("difficulty") == "easy":
                    difficulty = Difficulty.EASY
                elif q.get("difficulty") == "hard":
                    difficulty = Difficulty.HARD

                new_question = Question(
                    question_id=question_id,
                    record_id=None,  # 手动选题不关联考试记录
                    content=q.get("content", ""),
                    options=q.get("options"),
                    answer=str(q.get("answer", "")),
                    analysis=q.get("analysis"),
                    knowledge_points=q.get("knowledge_points", []),
                    difficulty=difficulty,
                    source=QuestionSource.MANUAL_SELECTED,
                    source_exam=question_set.name,
                    audit_status=AuditStatus.PASSED
                )
                db.add(new_question)

            # 创建关联
            current_max_order += 1
            set_item = QuestionSetItem(
                item_id=f"qsi_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}",
                set_id=request.set_id,
                question_id=question_id,
                sort_order=current_max_order
            )
            db.add(set_item)
            imported_count += 1

        # 更新真题集题目数量
        question_set.question_count = db.query(QuestionSetItem).filter(
            QuestionSetItem.set_id == request.set_id
        ).count()
        question_set.updated_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "message": f"成功导入 {imported_count} 道题目",
            "imported_count": imported_count
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"导入失败: {str(e)}"}


# ==================== 试卷分组查询 API ====================

@router.get("/papers", response_model=Dict)
async def get_papers_grouped():
    """获取所有真题试卷，按地区→年份分组"""
    from app.services.exam_bank import exam_bank_service
    groups = exam_bank_service.get_papers_grouped()
    total_papers = sum(len(y["papers"]) for g in groups for y in g["years"])
    total_questions = len(exam_bank_service.questions)
    return {
        "success": True,
        "data": {
            "total_papers": total_papers,
            "total_questions": total_questions,
            "groups": groups
        }
    }


# ==================== 历史真题查询 API ====================

@router.get("/historical", response_model=Dict)
async def get_historical_questions(
    region: Optional[str] = None,
    year: Optional[int] = None,
    knowledge_point: Optional[str] = None,
    difficulty: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
):
    """
    查询历年真题
    支持按地区、年份、知识点、难度筛选
    从 ExamBankService（内存加载JSON文件）读取，而非数据库表
    """
    from app.services.exam_bank import exam_bank_service

    # 参数映射：region 映射到 service 的 source（"全国卷" → 匹配 "全国卷2024"）
    results = exam_bank_service.search_questions(
        source=region,
        year=year,
        knowledge_point=knowledge_point,
        difficulty=difficulty
    )

    total = len(results)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_results = results[start:end]

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "questions": [
                {
                    "exam_id": q.exam_id,
                    "question_id": q.exam_id,
                    "source": q.source,
                    "year": q.year,
                    "region": q.region,
                    "question_number": q.question_number,
                    "question_type": q.question_type,
                    "content": q.content,
                    "options": q.options,
                    "answer": q.answer,
                    "analysis": q.analysis or "",
                    "knowledge_points": q.knowledge_points,
                    "difficulty": q.difficulty or "medium",
                    "discrimination": q.discrimination,
                    "page_image": q.page_image,
                }
                for q in page_results
            ]
        }
    }
