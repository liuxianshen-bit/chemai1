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

    # Collect class names + accuracy data in batch
    class_ids = set(s.class_id for s in students if s.class_id)
    class_names = {}
    if class_ids:
        from app.models.database import Class
        for c in db.query(Class).filter(Class.class_id.in_(class_ids)).all():
            class_names[c.class_id] = c.name

    # Batch accuracy per student
    accuracy_map = {}
    from sqlalchemy import text
    acc_rows = db.execute(text(
        "SELECT student_id, CAST(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS FLOAT)/MAX(1,COUNT(*)) as acc "
        "FROM student_answers GROUP BY student_id"
    )).fetchall()
    for row in acc_rows:
        if row[1] is not None:
            accuracy_map[row[0]] = round(row[1], 2)

    return {
        "success": True,
        "total": len(students),
        "students": [
            {
                "student_id": s.student_id,
                "name": s.name,
                "class_id": s.class_id,
                "class_name": class_names.get(s.class_id, ""),
                "phone": s.phone,
                "status": s.status,
                "barrier_type": s.barrier_type,
                "exercises_completed": s.exercises_completed,
                "last_exercise_at": s.last_exercise_at.isoformat() if s.last_exercise_at else None,
                "accuracy": accuracy_map.get(s.student_id),
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in students
        ]
    }


@router.get("/student/{student_id}/detail")
async def get_student_detail(student_id: str, db: Session = Depends(get_db)):
    """获取学生详情: 薄弱知识点 + 最近活动"""
    import json
    from sqlalchemy import text
    from collections import Counter
    s = db.query(Student).filter(Student.student_id == student_id).first()
    if not s: raise HTTPException(status_code=404, detail="学生不存在")
    wkp, activity = [], []
    rows = db.execute(text(
        "SELECT q.knowledge_points FROM student_answers sa JOIN questions q ON sa.question_id=q.question_id "
        "WHERE sa.student_id=:s AND sa.is_correct=0 ORDER BY sa.answered_at DESC LIMIT 30"
    ), {"s": student_id}).fetchall()
    kp_count = Counter()
    for (kj,) in rows:
        for k in (json.loads(kj) if isinstance(kj, str) else (kj or [])):
            kp_count[k] += 1
    wkp = [k for k, _ in kp_count.most_common(5)]
    act_rows = db.execute(text(
        "SELECT q.knowledge_points, q.difficulty, sa.is_correct, sa.answered_at FROM student_answers sa "
        "JOIN questions q ON sa.question_id=q.question_id WHERE sa.student_id=:s "
        "ORDER BY sa.answered_at DESC LIMIT 10"
    ), {"s": student_id}).fetchall()
    for row in act_rows:
        d = row[3]
        if isinstance(d, str): date_str = d[:10] if len(d) > 10 else (d[:5] if '-' in d else '')
        elif hasattr(d, 'strftime'): date_str = d.strftime("%m-%d")
        else: date_str = str(d)[:10]
        kps = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or [])
        kp_name = kps[0] if kps else "化学"
        diff_label = {"EASY":"基础","MEDIUM":"进阶","HARD":"拔高"}.get(row[1],"")
        status = "✓" if row[2] else "✗"
        desc = f"{status} {kp_name}{diff_label+'·' if diff_label else ''}练习"
        activity.append({"date": date_str, "desc": desc, "is_correct": row[2]})
    return {"success": True, "weak_knowledge_points": wkp, "recent_activity": activity}


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


@router.post("/student/{student_id}/reset-password")
async def reset_student_password(
    student_id: str,
    db: Session = Depends(get_db)
):
    """
    重置学生密码为默认密码 123456
    """
    from app.models.database import Account
    import hashlib

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    account = db.query(Account).filter(Account.student_id == student_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="学生账户不存在")

    account.password_hash = hashlib.sha256("123456".encode()).hexdigest()
    db.commit()

    return {"success": True, "message": f"学生 {student.name} 的密码已重置为 123456"}
