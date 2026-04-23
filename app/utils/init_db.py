"""
数据库初始化工具
创建演示数据：邵阳县第一中学
"""
import hashlib
from datetime import datetime
from app.models.database import (
    init_db, get_db, Account, Class, Teacher, Student,
    School, Grade, TeacherClassSubject
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

        print("\n" + "=" * 60)
        print("数据库初始化完成!")
        print("=" * 60)
        print(f"""
邵阳县第一中学演示数据:
  - 高一(1)班: 34人 (学号 202610101~202610134)
  - 高一(2)班: 33人 (学号 202610201~202610233)
  - 共计: 67名学生

演示账号:
  admin / admin123          - 系统管理员
  hai / hai123456           - 学科组长（海老师，化学）
  liu / 123456              - 任课教师（刘老师，化学）
  chen / 123456             - 任课教师（陈老师，数学）

学生账号:
  学号 / 123456 (如: 202610101 / 123456)
""")
    except Exception as e:
        db.rollback()
        print(f"\n初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
