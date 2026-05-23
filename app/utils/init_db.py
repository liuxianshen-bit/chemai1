"""
数据库初始化工具
创建演示数据：邵阳县第一中学
"""
import hashlib
import random
from datetime import datetime, timedelta
from app.models.database import (
    init_db, get_db, Account, Class, Teacher, Student,
    School, Grade, TeacherClassSubject, ExamRecord, Question,
    StudentAnswer, BarrierConfig, Difficulty, RecordType,
    QuestionSource, AuditStatus, BarrierType, Parent,
    StudentParentBinding
)

def hash_password(password: str) -> str:
    """哈希密码（SHA256）"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_school(db):
    """创建邵阳县第一中学"""
    school = db.query(School).filter(School.school_id == "shaoyang_001").first()
    if school:
        print(f"学校已存在: {school.name}")
        return school

    school = School(
        school_id="shaoyang_001",
        name="邵阳县第一中学",
        region="湖南省邵阳市邵阳县",
        address="邵阳县塘渡口镇",
        phone="0739-6821001",
        current_term="2025-2026学年 第二学期",
        subjects=["语文", "数学", "英语", "化学", "物理", "生物", "政治", "历史", "地理"]
    )
    db.add(school)
    db.commit()
    print(f"已创建学校: {school.name}")
    return school


def create_grades(db, school):
    """创建年级"""
    grades_data = [
        {"grade_id": "grade_2025_高一", "name": "高一", "year": 2025},
        {"grade_id": "grade_2024_高二", "name": "高二", "year": 2024},
        {"grade_id": "grade_2023_高三", "name": "高三", "year": 2023},
    ]

    for g_data in grades_data:
        grade = db.query(Grade).filter(Grade.grade_id == g_data["grade_id"]).first()
        if grade:
            print(f"年级已存在: {grade.name}")
        else:
            grade = Grade(
                grade_id=g_data["grade_id"],
                school_id=school.school_id,
                name=g_data["name"],
                year=g_data["year"],
                status=1
            )
            db.add(grade)
            db.commit()
            print(f"已创建年级: {grade.name}")


def create_teachers(db, school):
    """创建教师（包含不同角色）"""
    teachers_data = [
        {
            "teacher_id": "admin_001",
            "name": "系统管理员",
            "role": "admin",
            "phone": "13800000001"
        },
        {
            "teacher_id": "teacher_hai",
            "name": "海老师",
            "role": "学科组长",
            "subject": "化学",
            "phone": "13973900001"
        },
        {
            "teacher_id": "teacher_liu",
            "name": "刘老师",
            "role": "teacher",
            "subject": "化学",
            "phone": "13973900002"
        },
        {
            "teacher_id": "teacher_math",
            "name": "陈老师",
            "role": "teacher",
            "subject": "数学",
            "phone": "13973900003"
        },
    ]

    for t_data in teachers_data:
        teacher = db.query(Teacher).filter(Teacher.teacher_id == t_data["teacher_id"]).first()
        if teacher:
            print(f"教师已存在: {teacher.name} ({teacher.role})")
        else:
            teacher = Teacher(
                teacher_id=t_data["teacher_id"],
                school_id=school.school_id,
                name=t_data["name"],
                phone=t_data.get("phone"),
                role=t_data["role"],
                status="approved"
            )
            db.add(teacher)
            db.commit()
            print(f"已创建教师: {teacher.name} ({teacher.role})")


def create_classes(db):
    """创建班级"""
    classes_data = [
        # 高一(1)班 34人
        {"class_id": "class_2025_1", "name": "高一(1)班", "grade_id": "grade_2025_高一", "grade": "高一", "student_count": 34},
        # 高一(2)班 33人
        {"class_id": "class_2025_2", "name": "高一(2)班", "grade_id": "grade_2025_高一", "grade": "高一", "student_count": 33},
    ]

    for c_data in classes_data:
        class_obj = db.query(Class).filter(Class.class_id == c_data["class_id"]).first()
        if class_obj:
            print(f"班级已存在: {class_obj.name}")
        else:
            class_obj = Class(
                class_id=c_data["class_id"],
                name=c_data["name"],
                grade=c_data["grade"],
                grade_id=c_data["grade_id"],
                teacher_id=None,
                subject="化学",
                student_count=c_data["student_count"]
            )
            db.add(class_obj)
            db.commit()
            print(f"已创建班级: {class_obj.name} ({c_data['student_count']}人)")


def create_teacher_class_relations(db):
    """创建教师-班级-科目关联"""
    relations = [
        # 海老师 - 高一(1)班 班主任，教 高一(1)(2)班化学
        {
            "id": "tcs_001",
            "teacher_id": "teacher_hai",
            "class_id": "class_2025_1",
            "subject": "化学",
            "is_class_teacher": True
        },
        {
            "id": "tcs_002",
            "teacher_id": "teacher_hai",
            "class_id": "class_2025_2",
            "subject": "化学",
            "is_class_teacher": False
        },
        # 刘老师 - 高一(2)班 班主任，教 高一(2)班化学
        {
            "id": "tcs_003",
            "teacher_id": "teacher_liu",
            "class_id": "class_2025_2",
            "subject": "化学",
            "is_class_teacher": True
        },
        # 陈老师 - 高一(1)(2)班 数学
        {
            "id": "tcs_004",
            "teacher_id": "teacher_math",
            "class_id": "class_2025_1",
            "subject": "数学",
            "is_class_teacher": False
        },
        {
            "id": "tcs_005",
            "teacher_id": "teacher_math",
            "class_id": "class_2025_2",
            "subject": "数学",
            "is_class_teacher": False
        },
    ]

    for r_data in relations:
        relation = db.query(TeacherClassSubject).filter(
            TeacherClassSubject.id == r_data["id"]
        ).first()
        if relation:
            print(f"关联已存在: {r_data['id']}")
        else:
            relation = TeacherClassSubject(**r_data)
            db.add(relation)
            db.commit()
            print(f"已创建关联: 教师{r_data['teacher_id']} -> 班级{r_data['class_id']} ({r_data['subject']})")


def create_demo_accounts(db):
    """创建演示账号"""
    accounts_data = [
        # admin账号
        {
            "account_id": "acc_admin",
            "username": "admin",
            "password": "admin123",
            "role": "admin",
            "teacher_id": "admin_001",
            "student_id": None
        },
        # 海老师 - 学科组长
        {
            "account_id": "acc_hai",
            "username": "hai",
            "password": "hai123456",
            "role": "学科组长",
            "teacher_id": "teacher_hai",
            "student_id": None
        },
        # 刘老师
        {
            "account_id": "acc_liu",
            "username": "liu",
            "password": "123456",
            "role": "teacher",
            "teacher_id": "teacher_liu",
            "student_id": None
        },
        # 陈老师
        {
            "account_id": "acc_chen",
            "username": "chen",
            "password": "123456",
            "role": "teacher",
            "teacher_id": "teacher_math",
            "student_id": None
        },
    ]

    for a_data in accounts_data:
        account = db.query(Account).filter(Account.username == a_data["username"]).first()
        if account:
            print(f"账号已存在: {account.username} ({account.role})")
        else:
            account = Account(
                account_id=a_data["account_id"],
                username=a_data["username"],
                password_hash=hash_password(a_data["password"]),
                role=a_data["role"],
                teacher_id=a_data["teacher_id"],
                student_id=a_data.get("student_id"),
                status="active"
            )
            db.add(account)
            db.commit()
            print(f"已创建账号: {a_data['username']} / {a_data['password']} ({a_data['role']})")


# 高一(1)班34人学号: 202610101 ~ 202610134
CLASS_1_STUDENTS = [
    "202610101", "202610102", "202610103", "202610104", "202610105", "202610106", "202610107", "202610108",
    "202610109", "202610110", "202610111", "202610112", "202610113", "202610114", "202610115", "202610116",
    "202610117", "202610118", "202610119", "202610120", "202610121", "202610122", "202610123", "202610124",
    "202610125", "202610126", "202610127", "202610128", "202610129", "202610130", "202610131", "202610132",
    "202610133", "202610134"
]

# 高一(2)班33人学号: 202610201 ~ 202610233
CLASS_2_STUDENTS = [
    "202610201", "202610202", "202610203", "202610204", "202610205", "202610206", "202610207", "202610208",
    "202610209", "202610210", "202610211", "202610212", "202610213", "202610214", "202610215", "202610216",
    "202610217", "202610218", "202610219", "202610220", "202610221", "202610222", "202610223", "202610224",
    "202610225", "202610226", "202610227", "202610228", "202610229", "202610230", "202610231", "202610232",
    "202610233"
]

# 67个学生的真实姓名（常见中文姓名）
STUDENT_NAMES = [
    # 高一(1)班34人
    "李雨萱", "王思远", "张梦琪", "刘子轩", "陈浩然", "杨静怡", "黄志强", "周吴昊",
    "吴林峰", "郑晓峰", "王秀英", "李俊杰", "张雪梅", "刘佳伟", "陈思思", "杨浩然",
    "黄雨彤", "周涛", "吴敏", "郑建华", "王磊", "李婷", "张勇", "刘芳", "陈志强",
    "杨超", "黄丽", "周伟", "吴艳", "郑云", "王强", "李娟", "张强", "刘军",
    # 高一(2)班33人
    "陈伟", "林思琪", "黄志强", "周秀兰", "吴浩宇", "郑雅婷", "王志强", "李雅静",
    "张俊杰", "刘思远", "陈雨萱", "杨浩然", "黄静怡", "周子轩", "吴秀英", "郑佳伟",
    "王思思", "李浩然", "张雨彤", "刘涛", "陈敏", "杨建华", "黄磊", "周婷",
    "吴勇", "郑芳", "王超", "李艳", "张云", "刘强", "陈娟", "杨军"
]


def create_all_students(db):
    """创建全部67名学生"""
    all_students = []

    # 高一(1)班学生
    class_1_names = STUDENT_NAMES[:34]
    for i, (student_id, name) in enumerate(zip(CLASS_1_STUDENTS, class_1_names)):
        all_students.append({
            "student_id": student_id,
            "name": name,
            "class_id": "class_2025_1"
        })

    # 高一(2)班学生
    class_2_names = STUDENT_NAMES[34:67]
    for i, (student_id, name) in enumerate(zip(CLASS_2_STUDENTS, class_2_names)):
        all_students.append({
            "student_id": student_id,
            "name": name,
            "class_id": "class_2025_2"
        })

    created_count = 0
    for s_data in all_students:
        student = db.query(Student).filter(Student.student_id == s_data["student_id"]).first()
        if student:
            print(f"学生已存在: {student.name} ({student.student_id})")
        else:
            student = Student(
                student_id=s_data["student_id"],
                name=s_data["name"],
                class_id=s_data["class_id"],
                status="approved"
            )
            db.add(student)
            db.commit()
            print(f"已创建学生: {student.name} ({student.student_id})")
            created_count += 1

            # 创建学生账号
            account = Account(
                account_id=f"acc_{s_data['student_id']}",
                username=s_data["student_id"],
                password_hash=hash_password("123456"),
                role="student",
                student_id=s_data["student_id"],
                status="active"
            )
            db.add(account)
            db.commit()

    print(f"\n共创建 {created_count} 名学生，67个账号")
    return len(all_students)


# ==================== 演示考试/答题数据 ====================

def load_sql_file(filename):
    """加载 SQL 文件内容"""
    import os
    sql_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", filename)
    with open(sql_path, "r", encoding="utf-8") as f:
        return f.read()


def create_demo_parents(db):
    """创建演示家长账号（P5-6）"""
    import uuid

    # 检查是否已存在
    existing_parent = db.query(Parent).filter(Parent.phone == "13800138000").first()
    if existing_parent:
        print(f"家长账号已存在: {existing_parent.name} ({existing_parent.phone})")
        return

    # 1. 创建家长记录
    parent = Parent(
        parent_id="parent_demo_001",
        name="李国华",
        phone="13800138000",
        email="liguohua@example.com",
        password_hash=hash_password("123456"),
        status="active"
    )
    db.add(parent)
    db.commit()

    # 2. 创建家长账号
    parent_account = Account(
        account_id="acc_parent_demo",
        username="13800138000",
        password_hash=hash_password("123456"),
        role="parent",
        parent_id=parent.parent_id,
        status="active"
    )
    db.add(parent_account)

    # 3. 绑定到学生 202610101（李雨萱）
    binding = StudentParentBinding(
        binding_id=f"bind_{parent.parent_id}_202610101",
        student_id="202610101",
        parent_id=parent.parent_id,
        relation="父亲",
        status="active",
        bind_code=f"BIND{random.randint(100000, 999999)}"
    )
    db.add(binding)

    db.commit()
    print(f"已创建家长账号: 13800138000 / 123456 (李国华 → 李雨萱)")


def create_demo_exam_data(db):
    """创建演示考试/答题数据（两个班、两位老师）"""
    from sqlalchemy import text

    print("\n9. 创建演示考试数据...")

    # 检查是否已有数据
    if db.query(ExamRecord).count() > 0:
        print("考试记录已存在，跳过演示数据创建")
        return

    exam_date = datetime(2026, 3, 15, 8, 0, 0)

    # ===== 从 SQL 文件加载题目基础数据 =====
    sql_content = load_sql_file("demo_exam_data.sql")
    statements = []
    for line in sql_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            continue
        statements.append(stripped)
    db.execute(text("\n".join(statements)))
    db.flush()

    # 读取已创建的题目
    questions = db.query(Question).order_by(Question.question_id).all()
    print(f"  已加载 {len(questions)} 道题目")

    # ===== 9a. 创建两次考试（每个班一次） =====
    exams_data = [
        {
            "record_id": "demo_exam_001",
            "class_id": "class_2025_1",
            "name": "高一(1)班 第一次月考 - 化学",
            "teacher_id": "teacher_hai",
            "present": 34
        },
        {
            "record_id": "demo_exam_002",
            "class_id": "class_2025_2",
            "name": "高一(2)班 第一次月考 - 化学",
            "teacher_id": "teacher_liu",
            "present": 33
        }
    ]

    exam_map = {}
    for ed in exams_data:
        exam = ExamRecord(
            record_id=ed["record_id"],
            class_id=ed["class_id"],
            type=RecordType.EXAM,
            name=ed["name"],
            question_stats={},
            avg_score=0,
            total_students=ed["present"],
            present_students=ed["present"],
            source=QuestionSource.AI_GENERATED,
            exam_date=exam_date,
            generated_at=exam_date - timedelta(days=3),
            created_at=exam_date - timedelta(days=3)
        )
        db.add(exam)
        exam_map[ed["record_id"]] = ed

    # 题目关联到两次考试
    for q in questions:
        q.record_id = "demo_exam_001"  # 题目属于高一(1)班考试
        # 再创建一套副本题目给高一(2)班
        q2_id = q.question_id.replace("demo_q_", "demo_q2_")
        q2 = Question(
            question_id=q2_id,
            record_id="demo_exam_002",
            content=q.content,
            options=q.options,
            answer=q.answer,
            analysis=q.analysis,
            knowledge_points=q.knowledge_points,
            difficulty=q.difficulty,
            source=QuestionSource.AI_GENERATED,
            audit_status=AuditStatus.PASSED,
            coefficient_correct=True,
            condition_correct=True,
            product_correct=True,
            structure_correct=True
        )
        db.add(q2)

    db.flush()
    all_questions = db.query(Question).all()
    print(f"  已创建 2 场考试，共 {len(all_questions)} 道题目")

    # ===== 9b. 创建学生作答记录（两个班） =====
    students = db.query(Student).order_by(Student.student_id).all()

    # 错误率配置（用于高一1班）
    q_error_rates_1 = {
        "demo_q_001": 0.15, "demo_q_002": 0.40, "demo_q_003": 0.20,
        "demo_q_004": 0.45, "demo_q_005": 0.50, "demo_q_006": 0.10,
        "demo_q_007": 0.40, "demo_q_008": 0.65, "demo_q_009": 0.60,
        "demo_q_010": 0.70, "demo_q_011": 0.35, "demo_q_012": 0.20,
        "demo_q_013": 0.65, "demo_q_014": 0.15, "demo_q_015": 0.35,
    }
    # 高一2班调整错误率（略低，表现稍好）
    q_error_rates_2 = {k: max(0.05, v - 0.08) for k, v in q_error_rates_1.items()}

    wrong_answers = {
        "demo_q_001": ["A", "B", "D"], "demo_q_002": ["B", "C", "D"],
        "demo_q_003": ["A", "B", "C"], "demo_q_004": ["A", "C", "D"],
        "demo_q_005": ["A", "B", "C"], "demo_q_006": ["A", "B", "D"],
        "demo_q_007": ["A", "B", "D"], "demo_q_008": ["A", "C", "D"],
        "demo_q_009": ["A", "B", "D"], "demo_q_010": ["A", "C", "D"],
        "demo_q_011": ["A", "B", "C"], "demo_q_012": ["A", "C", "D"],
        "demo_q_013": ["A", "B", "C"], "demo_q_014": ["A", "B", "D"],
        "demo_q_015": ["A", "B", "C"],
    }

    barrier_map = {
        "demo_q_001": BarrierType.CONCEPT, "demo_q_005": BarrierType.CONCEPT,
        "demo_q_009": BarrierType.CONCEPT, "demo_q_002": BarrierType.READING,
        "demo_q_004": BarrierType.READING, "demo_q_011": BarrierType.READING,
        "demo_q_008": BarrierType.EXPRESSION, "demo_q_010": BarrierType.EXPRESSION,
        "demo_q_013": BarrierType.EXPRESSION,
    }

    random.seed(42)
    answer_count = 0
    total_correct = 0

    for student in students:
        # 确定学生所属班级，选择对应的考试ID和错误率
        if student.class_id == "class_2025_1":
            exam_id = "demo_exam_001"
            q_prefix = "demo_q_"
            error_rates = q_error_rates_1
        else:
            exam_id = "demo_exam_002"
            q_prefix = "demo_q2_"
            error_rates = q_error_rates_2

        consecutive_errors = 0
        consecutive_correct = 0

        for i, q in enumerate(questions):
            qid_base = q.question_id  # e.g. "demo_q_001"
            qid = qid_base
            # 对2班，题目ID是 demo_q2_001
            if student.class_id == "class_2025_2":
                qid = qid_base.replace("demo_q_", "demo_q2_")

            error_rate = error_rates.get(qid_base, 0.3)
            is_correct = random.random() > error_rate

            if is_correct:
                answer_text = q.answer
                consecutive_correct += 1
                consecutive_errors = 0
                barrier = None
            else:
                answer_text = random.choice(wrong_answers.get(qid_base, ["A"]))
                consecutive_errors += 1
                consecutive_correct = 0
                barrier = barrier_map.get(qid_base)

            answer = StudentAnswer(
                answer_id=f"sa_{student.student_id}_{qid}",
                student_id=student.student_id,
                question_id=qid,
                exam_record_id=exam_id,
                student_answer=answer_text,
                is_correct=is_correct,
                barrier_type=barrier,
                consecutive_errors=min(consecutive_errors, 5),
                consecutive_correct=min(consecutive_correct, 5),
                answered_at=exam_date + timedelta(minutes=i * 5 + random.randint(0, 3))
            )
            db.add(answer)
            answer_count += 1
            if is_correct:
                total_correct += 1

    db.flush()
    print(f"  已创建 {answer_count} 条作答记录 ({len(students)}学生 × {len(questions)}题)")

    # ===== 9c. 统计错题数据（按考试） =====
    for exam_id in ["demo_exam_001", "demo_exam_002"]:
        exam_record = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
        if not exam_record:
            continue

        q_prefix = "demo_q_" if exam_id == "demo_exam_001" else "demo_q2_"
        question_stats = {}

        for q in questions:
            qid = q.question_id.replace("demo_q_", q_prefix)
            answers = db.query(StudentAnswer).filter(
                StudentAnswer.question_id == qid,
                StudentAnswer.exam_record_id == exam_id
            ).all()
            total = len(answers)
            wrong = sum(1 for a in answers if not a.is_correct)
            question_stats[qid] = {
                "total": total,
                "correct": total - wrong,
                "wrong": wrong,
                "error_rate": round(wrong / total, 2) if total > 0 else 0
            }

        exam_record.question_stats = question_stats
        exam_record.avg_score = round(
            sum(1 for a in db.query(StudentAnswer).filter(
                StudentAnswer.exam_record_id == exam_id
            ).all() if a.is_correct) / max(
                db.query(StudentAnswer).filter(
                    StudentAnswer.exam_record_id == exam_id
                ).count(), 1
            ) * 100, 1
        )

    # ===== 9d. 创建两位老师的障碍诊断配置 =====
    for teacher_id in ["teacher_hai", "teacher_liu"]:
        config = BarrierConfig(
            config_id=f"bc_{teacher_id}",
            teacher_id=teacher_id,
            concept_threshold=3,
            reading_threshold=2,
            expression_threshold=3,
            mastery_threshold=3,
            auto_sync_to_student=True
        )
        db.add(config)

    db.commit()

    # 最终统计
    exam_1 = db.query(ExamRecord).filter(ExamRecord.record_id == "demo_exam_001").first()
    exam_2 = db.query(ExamRecord).filter(ExamRecord.record_id == "demo_exam_002").first()
    print(f"\n  ✅ 演示数据创建完成!")
    print(f"  - 考试1: 高一(1)班 ｜ 34人 ｜ 平均正确率 {exam_1.avg_score}%")
    print(f"  - 考试2: 高一(2)班 ｜ 33人 ｜ 平均正确率 {exam_2.avg_score}%")
    print(f"  - 题目: {len(questions)} 道 × 2套 = {len(all_questions)} 道")
    print(f"  - 作答: {answer_count} 条")
    print(f"  - 障碍诊断配置: 2 位老师")


def init_database():
    """初始化数据库并创建演示数据"""
    print("=" * 60)
    print("ChemAI 数据库初始化 - 邵阳县第一中学")
    print("=" * 60)

    print("\n1. 初始化数据库表...")
    init_db()

    db = next(get_db())
    try:
        print("\n2. 创建学校...")
        school = create_school(db)

        print("\n3. 创建年级...")
        create_grades(db, school)

        print("\n4. 创建教师...")
        create_teachers(db, school)

        print("\n5. 创建班级...")
        create_classes(db)

        print("\n6. 创建教师-班级关联...")
        create_teacher_class_relations(db)

        print("\n7. 创建演示账号...")
        create_demo_accounts(db)

        print("\n8. 创建67名学生...")
        total = create_all_students(db)

        print("\n9. 创建演示考试/答题数据...")
        create_demo_exam_data(db)

        print("\n10. 创建演示家长账号...")
        create_demo_parents(db)

        print("\n" + "=" * 60)
        print("数据库初始化完成!")
        print("=" * 60)
        print(f"""
邵阳县第一中学演示数据:
  - 高一(1)班: 34人 (学号 202610101~202610134)
  - 高一(2)班: 33人 (学号 202610201~202610233)
  - 共计: 67名学生, 2个班级
  - 考试1: 高一(1)班 第一次月考 - 化学 (15道题, 34人作答)
  - 考试2: 高一(2)班 第一次月考 - 化学 (15道题, 33人作答)
  - 作答: 1005条学生作答记录
  - 障碍诊断: 海老师 + 刘老师 配置

演示账号:
  admin / admin123          - 系统管理员
  hai / hai123456           - 学科组长（海老师，化学）
  liu / 123456              - 任课教师（刘老师，化学）
  chen / 123456             - 任课教师（陈老师，数学）

学生账号:
  学号 / 123456 (如: 202610101 / 123456)

家长账号:
  13800138000 / 123456      - 李国华（李雨萱的家长）
""")

    except Exception as e:
        db.rollback()
        print(f"\n初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
