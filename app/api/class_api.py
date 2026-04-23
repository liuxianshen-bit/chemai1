"""
班级管理API
GET /api/classes - 获取班级列表
POST /api/classes - 创建班级
PUT /api/classes/{id} - 更新班级
DELETE /api/classes/{id} - 删除班级
GET /api/classes/{id}/students - 获取班级学生
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import get_db, Class, Student, Teacher, TeacherClassSubject

router = APIRouter()


class ClassCreate(BaseModel):
    name: str
    grade_id: str  # 年级ID，如 "grade_2026_高一"
    subject: Optional[str] = "化学"


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    grade_id: Optional[str] = None
    subject: Optional[str] = None


@router.get("")
async def get_classes(
    teacher_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取班级列表
    当传入 teacher_id 时，通过 TeacherClassSubject 表联合查询
    """
    if teacher_id:
        # 通过 TeacherClassSubject 关联表查询该教师负责的所有班级
        tcs_records = db.query(TeacherClassSubject).filter(
            TeacherClassSubject.teacher_id == teacher_id
        ).all()
        class_ids = [r.class_id for r in tcs_records]

        if not class_ids:
            return {"success": True, "total": 0, "classes": []}

        classes = db.query(Class).filter(Class.class_id.in_(class_ids)).all()
    else:
        # 返回所有班级
        classes = db.query(Class).all()

    result = []
    for c in classes:
        # 获取班主任信息
        teacher = db.query(Teacher).filter(Teacher.teacher_id == c.teacher_id).first()
        # 获取该班级的所有任课教师（通过 TeacherClassSubject）
        tcs_records = db.query(TeacherClassSubject).filter(
            TeacherClassSubject.class_id == c.class_id
        ).all()
        teacher_ids = [r.teacher_id for r in tcs_records]
        teachers = db.query(Teacher).filter(Teacher.teacher_id.in_(teacher_ids)).all() if teacher_ids else []

        result.append({
            "class_id": c.class_id,
            "name": c.name,
            "teacher_id": c.teacher_id,  # 班主任ID
            "teacher_name": teacher.name if teacher else None,
            "grade": c.grade,
            "grade_id": c.grade_id,
            "subject": c.subject,
            "student_count": c.student_count or 0,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "teachers": [
                {
                    "teacher_id": t.teacher_id,
                    "name": t.name,
                    "subject": next((r.subject for r in tcs_records if r.teacher_id == t.teacher_id), None),
                    "is_class_teacher": t.teacher_id == c.teacher_id
                }
                for t in teachers
            ] if teachers else []
        })

    return {
        "success": True,
        "total": len(result),
        "classes": result
    }


@router.post("")
async def create_class(
    request: ClassCreate,
    db: Session = Depends(get_db)
):
    """
    创建班级
    """
    # 检查年级是否存在
    from app.models.database import Grade
    grade = db.query(Grade).filter(Grade.grade_id == request.grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="年级不存在")

    # 生成班级ID
    class_id = f"class_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    class_obj = Class(
        class_id=class_id,
        name=request.name,
        grade_id=request.grade_id,
        grade=grade.name,  # 从年级表获取年级名称
        subject=request.subject or "化学",
        student_count=0
    )
    db.add(class_obj)
    db.commit()

    return {
        "success": True,
        "message": "班级创建成功",
        "class_id": class_id
    }


@router.put("/{class_id}")
async def update_class(
    class_id: str,
    request: ClassUpdate,
    db: Session = Depends(get_db)
):
    """
    更新班级信息
    """
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    if request.name is not None:
        class_obj.name = request.name
    if request.grade_id is not None:
        # 检查新年级是否存在
        from app.models.database import Grade
        grade = db.query(Grade).filter(Grade.grade_id == request.grade_id).first()
        if not grade:
            raise HTTPException(status_code=404, detail="年级不存在")
        class_obj.grade_id = request.grade_id
        class_obj.grade = grade.name  # 更新年级名称
    if request.subject is not None:
        class_obj.subject = request.subject

    class_obj.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "班级信息已更新"}


@router.delete("/{class_id}")
async def delete_class(
    class_id: str,
    db: Session = Depends(get_db)
):
    """
    删除班级
    """
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    # 检查班级是否有学生
    if class_obj.student_count and class_obj.student_count > 0:
        raise HTTPException(status_code=400, detail="班级仍有学生，无法删除")

    db.delete(class_obj)
    db.commit()

    return {"success": True, "message": "班级已删除"}


@router.get("/{class_id}/students")
async def get_class_students(
    class_id: str,
    db: Session = Depends(get_db)
):
    """
    获取班级学生列表
    """
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    students = db.query(Student).filter(Student.class_id == class_id).all()

    return {
        "success": True,
        "class_id": class_id,
        "class_name": class_obj.name,
        "total": len(students),
        "students": [
            {
                "student_id": s.student_id,
                "name": s.name,
                "phone": s.phone,
                "status": s.status,
                "barrier_type": s.barrier_type,
                "exercises_completed": s.exercises_completed,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in students
        ]
    }
