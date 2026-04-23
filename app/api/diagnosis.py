"""
F4: 学生障碍类型AI诊断 API
基于PRD v1.0完整版功能规格
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import json
from sqlalchemy.orm import Session

from app.models.database import (
    Student, ExamRecord, StudentAnswer, Question, BarrierConfig, Class,
    get_db, BarrierType
)

router = APIRouter()


class StudentDiagnosis(BaseModel):
    """学生障碍诊断结果"""
    student_id: str
    student_name: str
    barrier_type: Dict[str, float]  # {concept: 0.3, reading: 0.5, expression: 0.2}
    dominant_barrier: str  # 主要障碍类型
    weak_knowledge_points: List[str]  # 薄弱知识点
    recommended_intervention: str  # 推荐干预策略
    last_updated: str


class BarrierDiagnosisResponse(BaseModel):
    """障碍诊断响应"""
    class_id: str
    exam_record_id: str
    students: List[StudentDiagnosis]
    class_barrier_distribution: Dict[str, int]  # {concept: 25, reading: 40, expression: 25}
    avg_mastery: float


class BarrierConfigRequest(BaseModel):
    """障碍诊断配置请求"""
    concept_threshold: int = 3  # 1-5
    reading_threshold: int = 2  # 1-5
    expression_threshold: int = 3  # 1-5
    mastery_threshold: int = 3  # 1-5
    auto_sync_to_student: bool = False


class LearningPlanRequest(BaseModel):
    """生成学习计划请求"""
    student_id: str
    barrier_type: str  # concept/reading/expression
    weak_knowledge_points: List[str]
    recent_performance: Optional[Dict] = None  # 可选的近期表现数据


class LearningPlanResponse(BaseModel):
    """学习计划响应"""
    student_id: str
    student_name: str
    plan: Dict  # LLM生成的学习计划
    generated_at: str


class BarrierConfigResponse(BaseModel):
    """障碍诊断配置响应"""
    teacher_id: str
    concept_threshold: int
    reading_threshold: int
    expression_threshold: int
    mastery_threshold: int
    auto_sync_to_student: bool


# 干预建议
_INTERVENTIONS = {
    BarrierType.CONCEPT.value: "建议加强基础概念复习，使用思维导图梳理知识体系，重点理解\"为什么\"而非死记硬背",
    BarrierType.READING.value: "建议练习审题技巧，使用划线法提取题目关键信息，注意题目中的限定词和隐含条件",
    BarrierType.EXPRESSION.value: "建议加强规范化表述训练，参考标准答案的表述方式，练习用专业化学用语回答"
}


@router.get("/barrier/{class_id}/{exam_record_id}", response_model=BarrierDiagnosisResponse)
async def diagnose_barrier_types(
    class_id: str,
    exam_record_id: str,
    db: Session = Depends(get_db)
):
    """
    班级学生障碍类型诊断
    输入: 班级ID + 考试记录ID
    输出: 每个学生的障碍类型占比 + 班级分布

    诊断规则（基于PRD F4）：
    - 概念理解型(concept): 错题集中在基础概念题，审题类题目正确率高
    - 审题障碍型(reading): 错题集中在长题干题目，概念类题目正确率高
    - 表述障碍型(expression): 错题集中在填空题/计算题，选择题正确率高
    """
    # 验证考试记录存在
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == exam_record_id,
        ExamRecord.class_id == class_id
    ).first()

    if not exam_record:
        raise HTTPException(status_code=404, detail=f"考试记录不存在")

    # 查询班级所有学生
    students = db.query(Student).filter(Student.class_id == class_id).all()

    if not students:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 没有学生")

    diagnoses = []
    total_barriers = {"concept": 0, "reading": 0, "expression": 0}
    total_mastery = 0.0

    for student in students:
        # 查询该学生的答题记录
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.student_id == student.student_id,
            StudentAnswer.exam_record_id == exam_record_id
        ).all()

        # 统计各类型错误
        errors_by_type = {"concept": 0, "reading": 0, "expression": 0}
        weak_kps = []
        kp_error_count: Dict[str, int] = {}

        for ans in answers:
            if ans.is_correct:
                continue

            # 获取题目信息
            question = db.query(Question).filter(
                Question.question_id == ans.question_id
            ).first()

            if not question:
                continue

            # 根据题目类型判断障碍
            barrier = ans.barrier_type
            if barrier:
                errors_by_type[barrier.value] += 1

            # 统计知识点错误
            for kp in (question.knowledge_points or []):
                kp_error_count[kp] = kp_error_count.get(kp, 0) + 1

        # 找出薄弱知识点（错误最多的）
        sorted_kps = sorted(kp_error_count.items(), key=lambda x: x[1], reverse=True)
        weak_kps = [kp for kp, _ in sorted_kps[:3]]

        # 计算障碍类型占比
        total_errors = sum(errors_by_type.values())
        if total_errors == 0:
            barrier_type = {"concept": 0.33, "reading": 0.33, "expression": 0.34}
        else:
            barrier_type = {
                k: round(v / total_errors, 2)
                for k, v in errors_by_type.items()
            }

        # 确定主要障碍
        dominant = max(barrier_type, key=barrier_type.get)
        if errors_by_type[dominant] == 0:
            dominant = "concept"  # 默认

        diagnoses.append(StudentDiagnosis(
            student_id=student.student_id,
            student_name=student.name,
            barrier_type=barrier_type,
            dominant_barrier=dominant,
            weak_knowledge_points=weak_kps,
            recommended_intervention=_INTERVENTIONS.get(dominant, ""),
            last_updated=datetime.now().strftime("%Y-%m-%d")
        ))

        total_barriers[dominant] += 1

        # 计算掌握度（简化版：答对题数/总题数）
        correct_count = len([a for a in answers if a.is_correct])
        mastery = correct_count / len(answers) if answers else 0
        total_mastery += mastery

    avg_mastery = total_mastery / len(students) if students else 0

    return BarrierDiagnosisResponse(
        class_id=class_id,
        exam_record_id=exam_record_id,
        students=diagnoses,
        class_barrier_distribution=total_barriers,
        avg_mastery=round(avg_mastery, 2)
    )


@router.get("/barrier/{student_id}")
async def get_student_barrier(student_id: str, db: Session = Depends(get_db)):
    """
    获取单个学生障碍类型详情
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 获取最新的障碍类型
    barrier_type = student.barrier_type or {"concept": 0.33, "reading": 0.33, "expression": 0.34}
    dominant = max(barrier_type, key=barrier_type.get)

    # TODO: 计算真正的薄弱知识点（基于历史答题数据）
    weak_kps = ["盐类水解", "电解池"]  # 简化版

    return StudentDiagnosis(
        student_id=student_id,
        student_name=student.name,
        barrier_type=barrier_type,
        dominant_barrier=dominant,
        weak_knowledge_points=weak_kps,
        recommended_intervention=_INTERVENTIONS.get(dominant, ""),
        last_updated=student.barrier_last_updated.strftime("%Y-%m-%d") if student.barrier_last_updated else datetime.now().strftime("%Y-%m-%d")
    )


@router.put("/config/{teacher_id}", response_model=BarrierConfigResponse)
async def update_barrier_config(
    teacher_id: str,
    config: BarrierConfigRequest,
    db: Session = Depends(get_db)
):
    """
    更新障碍诊断规则配置
    老师可调整各障碍类型的触发阈值
    """
    # 查询是否已存在配置
    existing = db.query(BarrierConfig).filter(
        BarrierConfig.teacher_id == teacher_id
    ).first()

    if existing:
        # 更新现有配置
        existing.concept_threshold = config.concept_threshold
        existing.reading_threshold = config.reading_threshold
        existing.expression_threshold = config.expression_threshold
        existing.mastery_threshold = config.mastery_threshold
        existing.auto_sync_to_student = config.auto_sync_to_student
        existing.updated_at = datetime.utcnow()
    else:
        # 创建新配置
        import uuid
        new_config = BarrierConfig(
            config_id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            concept_threshold=config.concept_threshold,
            reading_threshold=config.reading_threshold,
            expression_threshold=config.expression_threshold,
            mastery_threshold=config.mastery_threshold,
            auto_sync_to_student=config.auto_sync_to_student
        )
        db.add(new_config)

    db.commit()

    return BarrierConfigResponse(
        teacher_id=teacher_id,
        concept_threshold=config.concept_threshold,
        reading_threshold=config.reading_threshold,
        expression_threshold=config.expression_threshold,
        mastery_threshold=config.mastery_threshold,
        auto_sync_to_student=config.auto_sync_to_student
    )


@router.get("/config/{teacher_id}", response_model=BarrierConfigResponse)
async def get_barrier_config(teacher_id: str, db: Session = Depends(get_db)):
    """
    获取障碍诊断规则配置
    """
    config = db.query(BarrierConfig).filter(
        BarrierConfig.teacher_id == teacher_id
    ).first()

    if config:
        return BarrierConfigResponse(
            teacher_id=teacher_id,
            concept_threshold=config.concept_threshold,
            reading_threshold=config.reading_threshold,
            expression_threshold=config.expression_threshold,
            mastery_threshold=config.mastery_threshold,
            auto_sync_to_student=config.auto_sync_to_student
        )

    # 返回默认值
    return BarrierConfigResponse(
        teacher_id=teacher_id,
        concept_threshold=3,
        reading_threshold=2,
        expression_threshold=3,
        mastery_threshold=3,
        auto_sync_to_student=False
    )


@router.post("/learning-plan/generate", response_model=LearningPlanResponse)
async def generate_student_learning_plan(
    request: LearningPlanRequest,
    db: Session = Depends(get_db)
):
    """
    生成学生个性化学习计划
    基于学生障碍类型和薄弱知识点,使用LLM生成定制化学习路径
    """
    # 查询学生信息
    student = db.query(Student).filter(Student.student_id == request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {request.student_id} 不存在")

    # 调用LLM服务生成学习计划
    from app.services.llm_service import llm_service

    result = llm_service.generate_learning_plan(
        student_name=student.name,
        barrier_type=request.barrier_type,
        weak_knowledge_points=request.weak_knowledge_points,
        recent_performance=request.recent_performance
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"学习计划生成失败: {result.get('error', '未知错误')}")

    # 解析LLM返回的JSON计划
    plan_content = result.get("content", "{}")
    try:
        # 尝试提取JSON（处理可能的markdown格式）
        import re
        json_match = re.search(r'\{[\s\S]*\}', plan_content)
        if json_match:
            plan_data = json.loads(json_match.group())
        else:
            plan_data = {"raw_plan": plan_content}
    except json.JSONDecodeError:
        plan_data = {"raw_plan": plan_content}

    return LearningPlanResponse(
        student_id=request.student_id,
        student_name=student.name,
        plan=plan_data,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )


@router.post("/learning-plan/apply/{student_id}")
async def apply_student_learning_plan(
    student_id: str,
    plan_data: Dict,
    db: Session = Depends(get_db)
):
    """
    应用学习计划到学生
    将生成的学习计划保存并推送给学生
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # TODO: 将学习计划保存到学生记录中
    # 目前仅返回成功状态

    return {
        "success": True,
        "message": "学习计划已应用到学生",
        "student_id": student_id
    }


@router.post("/learning-plan/send-to-parent/{student_id}")
async def send_plan_to_parent(
    student_id: str,
    plan_data: Optional[Dict] = None,
    db: Session = Depends(get_db)
):
    """
    发送学生学习计划给家长
    推送至家长端App查看
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # TODO: 实现实际的推送逻辑（短信/邮件/App推送）
    # 目前仅返回模拟成功

    return {
        "success": True,
        "message": "学习计划已发送给家长",
        "student_id": student_id
    }


@router.get("/learning-plan/{student_id}")
async def get_student_learning_plan(
    student_id: str,
    db: Session = Depends(get_db)
):
    """
    获取学生当前学习计划
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # TODO: 从学生记录中获取已保存的学习计划
    # 目前返回模拟数据用于测试
    return {
        "success": True,
        "data": {
            "student_id": student_id,
            "student_name": student.name,
            "plan": {
                "plan_title": "氧化还原反应专项提升计划",
                "plan_period": "2周",
                "barrier_interventions": [
                    {
                        "barrier": "concept",
                        "strategy": "通过动画理解电子转移过程，建立化合价变化与电子转移的关联",
                        "practice_tips": "每天完成5道化合价判断练习"
                    }
                ],
                "daily_tasks": [
                    {
                        "day": "第1-3天",
                        "content": "理解氧化还原反应概念",
                        "duration": "约30分钟",
                        "resource_type": "视频"
                    },
                    {
                        "day": "第4-7天",
                        "content": "化合价变化判断专项练习",
                        "duration": "约40分钟",
                        "resource_type": "练习"
                    },
                    {
                        "day": "第2周",
                        "content": "电子转移方向综合练习",
                        "duration": "约45分钟",
                        "resource_type": "综合练习"
                    }
                ],
                "weekly_goals": [
                    {
                        "week": "第一周",
                        "goals": ["掌握化合价变化判断", "理解电子转移方向"],
                        "milestone": "能够快速判断常见反应的化合价变化"
                    },
                    {
                        "week": "第二周",
                        "goals": ["熟练配平氧化还原方程式", "综合应用"],
                        "milestone": "能够独立完成中等难度的氧化还原计算题"
                    }
                ],
                "motivation_tips": ["每天进步一点点！", "坚持就是胜利！"],
                "parent_communication_suggestion": "建议每天检查孩子完成情况，给予适当的鼓励"
            },
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    }
