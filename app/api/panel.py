"""
F7: 班级学情可视化面板 API
基于PRD v1.0完整版功能规格
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import (
    Student, Class, ExamRecord, Question, StudentAnswer,
    get_db
)

router = APIRouter()


class KnowledgePointStat(BaseModel):
    """知识点掌握统计"""
    knowledge_point: str
    class_error_rate: float
    trend: str  # improving/declining/stable
    related_barrier_distribution: Dict[str, float]


class StudentProgress(BaseModel):
    """学生进步情况"""
    student_id: str
    student_name: str
    rank_change: int  # 正数表示进步
    score_change: float
    improved_kps: List[str]
    declined_kps: List[str]


class ClassOverview(BaseModel):
    """班级总览视图"""
    class_id: str
    class_name: str
    total_students: int
    exam_count: int  # 历次考试次数
    avg_score_trend: List[float]  # 历次考试平均分
    recent_exam_avg: float
    recent_exam_date: str


class ClassLearningPanel(BaseModel):
    """班级学情面板完整响应"""
    class_overview: ClassOverview
    knowledge_points: List[KnowledgePointStat]
    top_errors: List[KnowledgePointStat]
    barrier_distribution: Dict[str, int]
    top_improvers: List[StudentProgress]
    top_declining: List[StudentProgress]


@router.get("/class/{class_id}", response_model=ClassLearningPanel)
async def get_class_learning_panel(
    class_id: str,
    time_range: Optional[str] = "all",  # all/term/month
    db: Session = Depends(get_db)
):
    """
    获取班级学情可视化面板
    支持按知识点/按学生/按时间三个维度查看
    """
    # 查询班级信息
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 不存在")

    # 查询班级所有考试记录
    exams = db.query(ExamRecord).filter(
        ExamRecord.class_id == class_id
    ).order_by(ExamRecord.exam_date).all()

    # 计算班级总览
    exam_count = len(exams)
    avg_score_trend = [e.avg_score for e in exams if e.avg_score]
    recent_exam_avg = exams[-1].avg_score if exams and exams[-1].avg_score else 0
    recent_exam_date = exams[-1].exam_date.strftime("%Y-%m-%d") if exams and exams[-1].exam_date else ""

    # 聚合知识点错误率
    kp_error_rates: Dict[str, List[float]] = {}
    for exam in exams:
        if exam.question_stats and isinstance(exam.question_stats, dict):
            for kp_stat in exam.question_stats.get("knowledge_point_stats", []):
                kp = kp_stat.get("knowledge_point", "")
                if kp:
                    if kp not in kp_error_rates:
                        kp_error_rates[kp] = []
                    kp_error_rates[kp].append(kp_stat.get("error_rate", 0))

    # 生成知识点统计
    knowledge_points = []
    for kp, rates in kp_error_rates.items():
        if not rates:
            continue
        avg_rate = sum(rates) / len(rates) if rates else 0
        trend = "stable"
        if len(rates) >= 2:
            if rates[-1] < rates[0]:
                trend = "improving"
            elif rates[-1] > rates[0]:
                trend = "declining"

        knowledge_points.append(KnowledgePointStat(
            knowledge_point=kp,
            class_error_rate=round(avg_rate, 3),
            trend=trend,
            related_barrier_distribution={"concept": 0.33, "reading": 0.33, "expression": 0.34}
        ))

    # 按错误率排序
    knowledge_points.sort(key=lambda x: x.class_error_rate, reverse=True)
    top_errors = knowledge_points[:5]

    # 计算障碍分布（简化版）
    barrier_distribution = {"concept": 25, "reading": 40, "expression": 25}

    # TODO: 计算top_improvers和top_declining（需要历史数据对比）

    return ClassLearningPanel(
        class_overview=ClassOverview(
            class_id=class_id,
            class_name=class_obj.name,
            total_students=class_obj.student_count or 0,
            exam_count=exam_count,
            avg_score_trend=avg_score_trend[-10:],  # 最多10次考试
            recent_exam_avg=round(recent_exam_avg, 1),
            recent_exam_date=recent_exam_date
        ),
        knowledge_points=knowledge_points[:10],  # 最多10个知识点
        top_errors=top_errors,
        barrier_distribution=barrier_distribution,
        top_improvers=[],
        top_declining=[]
    )


@router.get("/class/{class_id}/knowledge/{knowledge_point}")
async def get_knowledge_point_detail(
    class_id: str,
    knowledge_point: str,
    db: Session = Depends(get_db)
):
    """
    按知识点查看班级错误率分布
    高错误率知识点高亮标记
    """
    # 查询班级信息
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 不存在")

    # 查询班级所有考试记录
    exams = db.query(ExamRecord).filter(
        ExamRecord.class_id == class_id
    ).order_by(ExamRecord.exam_date).all()

    # 收集该知识点的错误率趋势
    error_rates = []
    exam_dates = []

    for exam in exams:
        if exam.question_stats and isinstance(exam.question_stats, dict):
            for kp_stat in exam.question_stats.get("knowledge_point_stats", []):
                if kp_stat.get("knowledge_point") == knowledge_point:
                    error_rates.append(kp_stat.get("error_rate", 0))
                    if exam.exam_date:
                        exam_dates.append(exam.exam_date.strftime("%Y-%m-%d"))
                    break

    # 查询该知识点出错的学生
    student_error_list = []
    for exam in exams:
        if not exam.question_stats:
            continue
        for kp_stat in exam.question_stats.get("knowledge_point_stats", []):
            if kp_stat.get("knowledge_point") == knowledge_point:
                # 找出错误的学生
                exam_questions = db.query(Question).filter(
                    Question.record_id == exam.record_id,
                    Question.knowledge_points.contains([knowledge_point])
                ).all()

                for q in exam_questions:
                    wrong_answers = db.query(StudentAnswer).filter(
                        StudentAnswer.question_id == q.question_id,
                        StudentAnswer.is_correct == False
                    ).all()

                    for ans in wrong_answers:
                        student = db.query(Student).filter(
                            Student.student_id == ans.student_id
                        ).first()
                        if student:
                            student_error_list.append({
                                "student_id": student.student_id,
                                "student_name": student.name,
                                "error_count": 1
                            })

    # 去重并汇总
    error_count_map: Dict[str, Dict] = {}
    for item in student_error_list:
        sid = item["student_id"]
        if sid in error_count_map:
            error_count_map[sid]["error_count"] += 1
        else:
            error_count_map[sid] = item

    avg_error_rate = sum(error_rates) / len(error_rates) if error_rates else 0

    return {
        "class_id": class_id,
        "class_name": class_obj.name,
        "knowledge_point": knowledge_point,
        "class_error_rate": round(avg_error_rate, 3),
        "error_rate_trend": error_rates[-10:],
        "student_error_list": list(error_count_map.values())[:20],  # 最多20个学生
        "related_barrier_distribution": {"concept": 0.33, "reading": 0.33, "expression": 0.34}
    }


@router.get("/class/{class_id}/student/{student_id}")
async def get_student_learning_detail(
    class_id: str,
    student_id: str,
    db: Session = Depends(get_db)
):
    """
    按学生查看学习详情
    包括错题历史和障碍类型变化曲线
    """
    # 查询学生信息
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生的所有练习/考试记录
    answers = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id
    ).order_by(StudentAnswer.answered_at).all()

    # 计算总练习次数和正确率
    total_exercises = len(answers)
    correct_count = sum(1 for a in answers if a.is_correct)
    avg_accuracy = correct_count / total_exercises if total_exercises > 0 else 0

    # 获取障碍类型
    barrier_type = student.barrier_type or {"concept": 0.33, "reading": 0.33, "expression": 0.34}

    # TODO: 计算barrier_trend（需要历史数据）

    # 获取薄弱知识点（基于错误最多的）
    kp_error_count: Dict[str, int] = {}
    for ans in answers:
        if ans.is_correct:
            continue
        question = db.query(Question).filter(Question.question_id == ans.question_id).first()
        if question and question.knowledge_points:
            for kp in question.knowledge_points:
                kp_error_count[kp] = kp_error_count.get(kp, 0) + 1

    sorted_kps = sorted(kp_error_count.items(), key=lambda x: x[1], reverse=True)
    weak_knowledge_points = [kp for kp, _ in sorted_kps[:5]]

    return {
        "student_id": student_id,
        "student_name": student.name,
        "total_exercises": total_exercises,
        "avg_accuracy": round(avg_accuracy, 2),
        "barrier_type": barrier_type,
        "barrier_trend": [],  # TODO: 需要历史数据
        "weak_knowledge_points": weak_knowledge_points,
        "improvement_suggestions": ["建议加强基础概念复习"]  # TODO: 基于障碍类型生成
    }


@router.get("/class/{class_id}/trend")
async def get_class_trend(class_id: str, db: Session = Depends(get_db)):
    """
    按时间维度查看班级学情变化
    同一知识点在历次考试中的错误率变化趋势
    判断教学干预是否有效
    """
    # 查询班级信息
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 不存在")

    # 查询班级所有考试记录
    exams = db.query(ExamRecord).filter(
        ExamRecord.class_id == class_id
    ).order_by(ExamRecord.exam_date).all()

    # 收集知识点错误率趋势
    kp_trends: Dict[str, Dict] = {}
    for exam in exams:
        if exam.question_stats and isinstance(exam.question_stats, dict):
            for kp_stat in exam.question_stats.get("knowledge_point_stats", []):
                kp = kp_stat.get("knowledge_point", "")
                if kp:
                    if kp not in kp_trends:
                        kp_trends[kp] = {
                            "error_rates": [],
                            "exam_dates": []
                        }
                    kp_trends[kp]["error_rates"].append(kp_stat.get("error_rate", 0))
                    if exam.exam_date:
                        kp_trends[kp]["exam_dates"].append(exam.exam_date.strftime("%Y-%m-%d"))

    # 构建响应
    knowledge_points_trend = []
    for kp, data in kp_trends.items():
        if not data["error_rates"]:
            continue
        trend = "stable"
        rates = data["error_rates"]
        if len(rates) >= 2:
            if rates[-1] < rates[0]:
                trend = "improving"
            elif rates[-1] > rates[0]:
                trend = "declining"

        knowledge_points_trend.append({
            "knowledge_point": kp,
            "error_rates": rates[-10:],  # 最多10次
            "exam_dates": data["exam_dates"][-10:],
            "intervention": ""  # TODO: 需要干预记录功能
        })

    # 整体趋势
    overall_trend = "stable"
    if knowledge_points_trend:
        improving_count = sum(1 for kp in knowledge_points_trend if kp["trend"] == "improving")
        declining_count = sum(1 for kp in knowledge_points_trend if kp["trend"] == "declining")
        if improving_count > declining_count:
            overall_trend = "improving"
        elif declining_count > improving_count:
            overall_trend = "declining"

    return {
        "class_id": class_id,
        "class_name": class_obj.name,
        "knowledge_points_trend": knowledge_points_trend,
        "overall_trend": overall_trend
    }


@router.get("/export/{class_id}")
async def export_class_report(class_id: str, format: str = "pdf"):
    """
    导出班级学情报告
    支持PDF格式
    """
    # TODO: 生成PDF报告
    return {
        "success": True,
        "download_url": f"/api/panel/download/class_{class_id}_report.pdf",
        "message": "PDF导出功能待实现"
    }


@router.get("/dashboard/{teacher_id}")
async def get_teacher_dashboard(
    teacher_id: str,
    db: Session = Depends(get_db)
):
    """
    获取教师概览仪表盘数据
    用于teacher.html首页概览统计
    """
    from datetime import datetime, timedelta

    # 查询教师管理的班级
    classes = db.query(Class).filter(Class.teacher_id == teacher_id).all()

    # 始终包含 demo_class 以显示演示数据
    class_ids = [c.class_id for c in classes]
    if 'demo_class' not in class_ids:
        class_ids.append('demo_class')

    if not class_ids:
        # 如果没有班级，返回空数据
        return {
            "success": True,
            "data": {
                "class_avg_score": 0,
                "class_avg_score_trend": 0,
                "total_students": 0,
                "weekly_practice": 0,
                "completion_rate": 0,
                "barrier_distribution": {
                    "concept": 0,
                    "reading": 0,
                    "expression": 0
                },
                "recent_exams": [],
                "pending_diagnosis": []
            }
        }

    # 查询班级学生总数
    total_students = db.query(Student).filter(Student.class_id.in_(class_ids)).count()

    # 查询最近考试（最近30天）
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_exams = db.query(ExamRecord).filter(
        ExamRecord.class_id.in_(class_ids),
        ExamRecord.exam_date >= thirty_days_ago
    ).order_by(ExamRecord.exam_date.desc()).limit(5).all()

    # 计算班级平均分（取最新考试的平均分）
    class_avg_score = 0
    class_avg_score_trend = 0
    if recent_exams:
        scores = [e.avg_score for e in recent_exams if e.avg_score]
        if scores:
            class_avg_score = round(sum(scores) / len(scores), 1)
        if len(scores) >= 2:
            class_avg_score_trend = round(scores[0] - scores[1], 1)

    # 计算本周练习次数（学生答题记录）
    week_ago = datetime.now() - timedelta(days=7)
    weekly_practice = db.query(StudentAnswer).filter(
        StudentAnswer.answered_at >= week_ago
    ).count()

    # 计算完成率（已完成的练习/布置的练习）
    total_exercises = db.query(StudentAnswer).filter(
        StudentAnswer.answered_at >= thirty_days_ago
    ).count()
    completion_rate = 0
    if total_exercises > 0 and total_students > 0:
        completion_rate = min(100, round((total_exercises / (total_students * 10)) * 100))

    # 计算障碍分布（从学生的障碍类型统计）
    students_with_barrier = db.query(Student).filter(
        Student.class_id.in_(class_ids),
        Student.barrier_type.isnot(None)
    ).all()

    barrier_counts = {"concept": 0, "reading": 0, "expression": 0}
    for s in students_with_barrier:
        bt = s.barrier_type
        if isinstance(bt, dict):
            for k, v in bt.items():
                if k in barrier_counts:
                    barrier_counts[k] += int(v)
        elif isinstance(bt, str):
            try:
                bt_dict = eval(bt)
                if isinstance(bt_dict, dict):
                    for k, v in bt_dict.items():
                        if k in barrier_counts:
                            barrier_counts[k] += int(v)
            except:
                pass

    total_barrier = sum(barrier_counts.values())
    barrier_distribution = {
        "concept": round(barrier_counts["concept"] / total_barrier * 100) if total_barrier > 0 else 0,
        "reading": round(barrier_counts["reading"] / total_barrier * 100) if total_barrier > 0 else 0,
        "expression": round(barrier_counts["expression"] / total_barrier * 100) if total_barrier > 0 else 0
    }

    # 近期考试列表
    recent_exams_list = []
    for e in recent_exams:
        recent_exams_list.append({
            "name": e.name or "未命名考试",
            "date": e.exam_date.strftime("%m-%d") if e.exam_date else "-",
            "avg_score": e.avg_score or 0,
            "status": "已完成"
        })

    # 待诊断错题（从最近的答题记录中提取错误最多的题目）
    recent_wrong_answers = db.query(StudentAnswer).filter(
        StudentAnswer.is_correct == False,
        StudentAnswer.answered_at >= thirty_days_ago
    ).all()

    kp_error_count = {}
    for ans in recent_wrong_answers:
        question = db.query(Question).filter(Question.question_id == ans.question_id).first()
        if question and question.knowledge_points:
            for kp in question.knowledge_points:
                kp_error_count[kp] = kp_error_count.get(kp, 0) + 1

    # 取错误最多的5个知识点
    sorted_kps = sorted(kp_error_count.items(), key=lambda x: x[1], reverse=True)[:5]
    pending_diagnosis = [
        {"knowledge_point": kp, "error_count": count}
        for kp, count in sorted_kps
    ]

    return {
        "success": True,
        "data": {
            "class_avg_score": class_avg_score,
            "class_avg_score_trend": class_avg_score_trend,
            "total_students": total_students,
            "weekly_practice": weekly_practice,
            "completion_rate": completion_rate,
            "barrier_distribution": barrier_distribution,
            "recent_exams": recent_exams_list,
            "pending_diagnosis": pending_diagnosis
        }
    }
