"""
考试管理 API
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import uuid

from app.models.database import ExamRecord, Class, Student, get_db, RecordType

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
