"""
用户管理API
GET /api/users/students - 获取学生列表
GET /api/users/teachers - 获取教师列表
POST /api/users/student - 创建学生
PUT /api/users/student/{id} - 更新学生
DELETE /api/users/student/{id} - 删除学生
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import get_db, Teacher, Student, Account, Class, TeacherClassSubject

router = APIRouter()


class StudentCreate(BaseModel):
    name: str
    class_id: str
    phone: Optional[str] = None


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    class_id: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None


class TeacherCreate(BaseModel):
    name: str
    school_id: Optional[str] = None
    phone: Optional[str] = None


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    school_id: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None


@router.get("/students")
async def get_students(
    class_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取学生列表
    """
    query = db.query(Student)

    if class_id:
        query = query.filter(Student.class_id == class_id)
    if status:
        query = query.filter(Student.status == status)

    students = query.all()

    return {
        "success": True,
        "total": len(students),
        "students": [
            {
                "student_id": s.student_id,
                "name": s.name,
                "class_id": s.class_id,
                "phone": s.phone,
                "status": s.status,
                "barrier_type": s.barrier_type,
                "exercises_completed": s.exercises_completed,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in students
        ]
    }


@router.get("/teachers")
async def get_teachers(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取教师列表
    """
    query = db.query(Teacher)

    if status:
        query = query.filter(Teacher.status == status)

    teachers = query.all()

    return {
        "success": True,
        "total": len(teachers),
        "teachers": [
            {
                "teacher_id": t.teacher_id,
                "name": t.name,
                "school_id": t.school_id,
                "phone": t.phone,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in teachers
        ]
    }


@router.post("/student")
async def create_student(
    request: StudentCreate,
    db: Session = Depends(get_db)
):
    """
    创建学生
    """
    # 检查班级是否存在
    class_obj = db.query(Class).filter(Class.class_id == request.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    # 生成学生ID
    student_id = f"student_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    student = Student(
        student_id=student_id,
        name=request.name,
        class_id=request.class_id,
        phone=request.phone,
        status="approved"  # 直接approved，也可以设为pending
    )
    db.add(student)

    # 更新班级学生数
    class_obj.student_count = (class_obj.student_count or 0) + 1

    db.commit()

    return {
        "success": True,
        "message": "学生创建成功",
        "student_id": student_id
    }


@router.put("/student/{student_id}")
async def update_student(
    student_id: str,
    request: StudentUpdate,
    db: Session = Depends(get_db)
):
    """
    更新学生信息
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    if request.name is not None:
        student.name = request.name
    if request.phone is not None:
        student.phone = request.phone
    if request.status is not None:
        student.status = request.status
    if request.class_id is not None:
        # 如果更换班级
        if request.class_id != student.class_id:
            # 减少原班级人数
            old_class = db.query(Class).filter(Class.class_id == student.class_id).first()
            if old_class and old_class.student_count:
                old_class.student_count = max(0, old_class.student_count - 1)

            # 增加新班级人数
            new_class = db.query(Class).filter(Class.class_id == request.class_id).first()
            if new_class:
                new_class.student_count = (new_class.student_count or 0) + 1

            student.class_id = request.class_id

    student.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "学生信息已更新"}


@router.delete("/student/{student_id}")
async def delete_student(
    student_id: str,
    db: Session = Depends(get_db)
):
    """
    删除学生
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 删除关联账户
    db.query(Account).filter(Account.student_id == student_id).delete()

    # 减少班级人数
    class_obj = db.query(Class).filter(Class.class_id == student.class_id).first()
    if class_obj and class_obj.student_count:
        class_obj.student_count = max(0, class_obj.student_count - 1)

    # 删除学生
    db.delete(student)
    db.commit()

    return {"success": True, "message": "学生已删除"}


@router.put("/teacher/{teacher_id}")
async def update_teacher(
    teacher_id: str,
    request: TeacherUpdate,
    db: Session = Depends(get_db)
):
    """
    更新教师信息
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    if request.name is not None:
        teacher.name = request.name
    if request.school_id is not None:
        teacher.school_id = request.school_id
    if request.phone is not None:
        teacher.phone = request.phone
    if request.status is not None:
        teacher.status = request.status

    teacher.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "教师信息已更新"}


@router.post("/teacher/approve/{teacher_id}")
async def approve_teacher(
    teacher_id: str,
    db: Session = Depends(get_db)
):
    """
    审批通过教师
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    teacher.status = "approved"
    teacher.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "教师已审批通过"}


@router.post("/student/approve/{student_id}")
async def approve_student(
    student_id: str,
    db: Session = Depends(get_db)
):
    """
    审批通过学生
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    student.status = "approved"
    student.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "学生已审批通过"}


# ============================================
# 教师-班级关联管理
# ============================================

class TeacherClassAssign(BaseModel):
    class_id: str
    subject: str
    is_class_teacher: bool = False


@router.post("/teacher/{teacher_id}/assign-classes")
async def assign_teacher_classes(
    teacher_id: str,
    assignments: list[TeacherClassAssign],
    db: Session = Depends(get_db)
):
    """
    分配教师到班级/科目
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    # 删除旧的关联
    db.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id
    ).delete()

    # 添加新的关联
    for assignment in assignments:
        tcs = TeacherClassSubject(
            id=f"tcs_{teacher_id}_{assignment.class_id}_{assignment.subject}",
            teacher_id=teacher_id,
            class_id=assignment.class_id,
            subject=assignment.subject,
            is_class_teacher=assignment.is_class_teacher,
            assigned_at=datetime.utcnow()
        )
        db.add(tcs)

    db.commit()
    return {"success": True, "message": f"已分配{len(assignments)}个班级/科目"}


@router.get("/teacher/{teacher_id}/classes")
async def get_teacher_classes(
    teacher_id: str,
    db: Session = Depends(get_db)
):
    """
    获取教师任教的班级列表
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    tcs_list = db.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id
    ).all()

    result = []
    for tcs in tcs_list:
        class_obj = db.query(Class).filter(Class.class_id == tcs.class_id).first()
        if class_obj:
            result.append({
                "tcs_id": tcs.id,
                "class_id": tcs.class_id,
                "class_name": class_obj.name,
                "subject": tcs.subject,
                "is_class_teacher": tcs.is_class_teacher,
                "grade_id": class_obj.grade_id
            })

    return {"success": True, "classes": result}


# ============================================
# 学生批量导入
# ============================================

class StudentBatchImport(BaseModel):
    class_id: str
    students: list[dict]  # [{"name": "张三", "phone": "13800138000"}, ...]


@router.post("/students/batch-import")
async def batch_import_students(
    import_data: StudentBatchImport,
    db: Session = Depends(get_db)
):
    """
    批量导入学生
    """
    # 检查班级是否存在
    class_obj = db.query(Class).filter(Class.class_id == import_data.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    imported = []
    failed = []

    for i, student_data in enumerate(import_data.students):
        try:
            name = student_data.get("name")
            phone = student_data.get("phone")

            if not name:
                failed.append({"index": i, "reason": "姓名为空"})
                continue

            student_id = f"student_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"
            student = Student(
                student_id=student_id,
                name=name,
                class_id=import_data.class_id,
                phone=phone,
                status="approved"
            )
            db.add(student)
            imported.append({"name": name, "student_id": student_id})
        except Exception as e:
            failed.append({"index": i, "reason": str(e)})

    # 更新班级学生数
    class_obj.student_count = (class_obj.student_count or 0) + len(imported)
    db.commit()

    return {
        "success": True,
        "message": f"导入完成：成功{len(imported)}个，失败{len(failed)}个",
        "imported": imported,
        "failed": failed
    }


# ============================================
# 学生调班
# ============================================

class StudentTransfer(BaseModel):
    new_class_id: str


@router.post("/student/{student_id}/transfer")
async def transfer_student(
    student_id: str,
    request: StudentTransfer,
    db: Session = Depends(get_db)
):
    """
    学生调班
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 检查新班级是否存在
    new_class = db.query(Class).filter(Class.class_id == request.new_class_id).first()
    if not new_class:
        raise HTTPException(status_code=404, detail="目标班级不存在")

    old_class_id = student.class_id

    # 减少原班级人数
    old_class = db.query(Class).filter(Class.class_id == old_class_id).first()
    if old_class and old_class.student_count:
        old_class.student_count = max(0, old_class.student_count - 1)

    # 增加新班级人数
    new_class.student_count = (new_class.student_count or 0) + 1

    # 更新学生班级
    student.class_id = request.new_class_id
    student.updated_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "message": f"学生已从{old_class_id}调至{request.new_class_id}"
    }
