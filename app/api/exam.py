"""
考试管理 API
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import uuid

from app.models.database import ExamRecord, Class, Student, StudentAnswer, Question, get_db, RecordType

router = APIRouter()


class ExamCreateRequest(BaseModel):
    """创建考试请求"""
    class_id: str
    name: str
    exam_date: Optional[datetime] = None


class ExamResponse(BaseModel):
    """考试响应"""
    record_id: str
    class_id: str
    name: str
    type: str
    total_students: int
    present_students: int
    avg_score: Optional[float] = None
    exam_date: Optional[datetime] = None


@router.post("/create", response_model=ExamResponse)
async def create_exam(request: ExamCreateRequest, db: Session = Depends(get_db)):
    """创建新考试记录"""
    # 验证班级存在
    class_obj = db.query(Class).filter(Class.class_id == request.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {request.class_id} 不存在")

    # 获取学生数量
    total_students = db.query(Student).filter(Student.class_id == request.class_id).count()

    # 创建考试记录
    record_id = f"exam_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    exam_record = ExamRecord(
        record_id=record_id,
        class_id=request.class_id,
        name=request.name,
        type=RecordType.EXAM,
        total_students=total_students,
        present_students=0,
        exam_date=request.exam_date or datetime.now()
    )

    db.add(exam_record)
    db.commit()
    db.refresh(exam_record)

    return ExamResponse(
        record_id=exam_record.record_id,
        class_id=exam_record.class_id,
        name=exam_record.name,
        type=exam_record.type.value,
        total_students=exam_record.total_students or 0,
        present_students=exam_record.present_students or 0,
        avg_score=exam_record.avg_score,
        exam_date=exam_record.exam_date
    )


@router.get("/list/{class_id}")
async def list_exams(class_id: str, db: Session = Depends(get_db)):
    """获取班级考试列表"""
    # 验证班级存在
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 不存在")

    # 查询考试记录
    exams = db.query(ExamRecord).filter(
        ExamRecord.class_id == class_id
    ).order_by(ExamRecord.exam_date.desc()).all()

    return {
        "class_id": class_id,
        "class_name": class_obj.name,
        "total_exams": len(exams),
        "exams": [
            {
                "record_id": e.record_id,
                "name": e.name,
                "total_students": e.total_students or 0,
                "present_students": e.present_students or 0,
                "avg_score": e.avg_score,
                "exam_date": e.exam_date.strftime("%Y-%m-%d") if e.exam_date else None
            }
            for e in exams
        ]
    }


@router.get("/{exam_record_id}")
async def get_exam(exam_record_id: str, db: Session = Depends(get_db)):
    """获取考试详情"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_record_id} 不存在")

    return {
        "record_id": exam.record_id,
        "class_id": exam.class_id,
        "name": exam.name,
        "type": exam.type.value,
        "total_students": exam.total_students or 0,
        "present_students": exam.present_students or 0,
        "avg_score": exam.avg_score,
        "exam_date": exam.exam_date.strftime("%Y-%m-%d") if exam.exam_date else None,
        "question_stats": exam.question_stats
    }


@router.post("/{exam_record_id}/finalize")
async def finalize_exam(exam_record_id: str, db: Session = Depends(get_db)):
    """完成考试录入，更新统计信息"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_record_id} 不存在")

    # 计算实际参考人数
    from app.models.database import StudentAnswer
    present_students = db.query(StudentAnswer.student_id).filter(
        StudentAnswer.exam_record_id == exam_record_id
    ).distinct().count()

    exam.present_students = present_students

    # TODO: 计算平均分（需要根据答题情况计算）

    db.commit()

    return {
        "success": True,
        "record_id": exam_record_id,
        "present_students": present_students
    }


# ============================================================
# P5-2: 考试管理补充端点
# ============================================================


class ExamUpdateRequest(BaseModel):
    """更新考试请求"""
    name: Optional[str] = None
    exam_date: Optional[datetime] = None


@router.put("/{exam_id}")
async def update_exam(exam_id: str, request: ExamUpdateRequest, db: Session = Depends(get_db)):
    """更新考试信息（名称、日期等）"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    if request.name is not None:
        exam.name = request.name
    if request.exam_date is not None:
        exam.exam_date = request.exam_date

    db.commit()
    db.refresh(exam)

    return {
        "success": True,
        "record_id": exam.record_id,
        "name": exam.name,
        "exam_date": exam.exam_date.strftime("%Y-%m-%d") if exam.exam_date else None
    }


@router.delete("/{exam_id}")
async def delete_exam(exam_id: str, db: Session = Depends(get_db)):
    """删除考试及相关数据（题目、答题记录）"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    # 删除关联的学生答题记录
    db.query(StudentAnswer).filter(StudentAnswer.exam_record_id == exam_id).delete()
    # 删除关联的题目
    db.query(Question).filter(Question.record_id == exam_id).delete()
    # 删除考试记录
    db.delete(exam)
    db.commit()

    return {"success": True, "message": f"考试 {exam_id} 已删除"}


@router.get("/{exam_id}/result/{student_id}")
async def get_student_exam_result(exam_id: str, student_id: str, db: Session = Depends(get_db)):
    """获取单个学生在某次考试中的结果详情"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生的答题记录
    answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_id,
        StudentAnswer.student_id == student_id
    ).all()

    # 查询考试题目
    questions = db.query(Question).filter(Question.record_id == exam_id).all()
    question_map = {q.question_id: q for q in questions}

    question_results = []
    correct_count = 0
    total_score = 0

    for ans in answers:
        q = question_map.get(ans.question_id)
        kps = q.knowledge_points if q else []
        if ans.is_correct:
            correct_count += 1
            total_score += 1

        question_results.append({
            "question_id": ans.question_id,
            "content": q.content if q else "",
            "options": q.options if q else None,
            "answer": q.answer if q else "",
            "analysis": q.analysis if q else "",
            "knowledge_points": kps,
            "your_answer": ans.student_answer,
            "is_correct": ans.is_correct,
            "barrier_type": ans.barrier_type.value if ans.barrier_type else None
        })

    total = len(answers)
    accuracy = round(correct_count / total, 2) if total > 0 else 0

    return {
        "success": True,
        "exam_id": exam_id,
        "exam_name": exam.name,
        "student_id": student_id,
        "student_name": student.name,
        "total_questions": total,
        "correct_count": correct_count,
        "accuracy": accuracy,
        "score": round(accuracy * 100, 1),
        "questions": question_results
    }
