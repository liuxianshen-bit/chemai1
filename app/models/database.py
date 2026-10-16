"""
ChemAI Database Models
基于PRD v1.0完整版附录D数据字典
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Text, JSON, ForeignKey, Enum, create_engine, LargeBinary
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from enum import Enum as PyEnum

Base = declarative_base()


class BarrierType(PyEnum):
    """障碍类型枚举"""
    CONCEPT = "concept"        # 概念理解型
    READING = "reading"        # 审题障碍型
    EXPRESSION = "expression"  # 表述障碍型


class RecordType(PyEnum):
    """记录类型枚举"""
    EXAM = "exam"       # 月考
    PRACTICE = "practice"  # 练习
    ASSIGNMENT = "assignment"  # 作业


class QuestionSource(PyEnum):
    """题目来源枚举"""
    AI_GENERATED = "ai_generated"
    MANUAL_SELECTED = "manual_selected"
    DAILY_PRACTICE = "daily_practice"
    OCR_IMPORT = "ocr_import"


class AuditStatus(PyEnum):
    """审核状态枚举"""
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


class Difficulty(PyEnum):
    """难度枚举"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    COMPETITION = "competition"


class Teacher(Base):
    """教师表"""
    __tablename__ = "teachers"

    teacher_id = Column(String(64), primary_key=True)
    school_id = Column(String(64), ForeignKey("schools.school_id"), nullable=True)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=True)
    status = Column(String(32), default="approved")  # pending/approved/rejected
    role = Column(String(32), default="teacher")  # admin/教务管理员/学科组长/teacher
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    classes = relationship("Class", back_populates="teacher")
    school = relationship("School", back_populates="teachers")
    teacher_subjects = relationship("TeacherClassSubject", back_populates="teacher")
    barrier_configs = relationship("BarrierConfig", back_populates="teacher")
    account = relationship("Account", back_populates="teacher", uselist=False)


class Student(Base):
    """学生表"""
    __tablename__ = "students"

    student_id = Column(String(64), primary_key=True)
    class_id = Column(String(64), ForeignKey("classes.class_id"), nullable=False)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=True)
    status = Column(String(32), default="approved")  # pending/approved/rejected
    # 障碍类型占比 (JSON: {concept: 0.3, reading: 0.5, expression: 0.2})
    barrier_type = Column(JSON, default={"concept": 0.33, "reading": 0.33, "expression": 0.34})
    barrier_last_updated = Column(DateTime, nullable=True)
    exercises_completed = Column(Integer, default=0)
    last_exercise_at = Column(DateTime, nullable=True)
    bind_code = Column(String(64), nullable=True)  # 家长绑定码
    current_plan = Column(JSON, nullable=True)  # 当前学习计划 {plan_title, daily_tasks, ...}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    student_class = relationship("Class", back_populates="students")
    account = relationship("Account", back_populates="student", uselist=False)
    parent_bindings = relationship("StudentParentBinding", back_populates="student")


class Account(Base):
    """账户表（登录认证）"""
    __tablename__ = "accounts"

    account_id = Column(String(64), primary_key=True)
    role = Column(String(32), nullable=False)  # admin/teacher/student/parent
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    teacher_id = Column(String(64), ForeignKey("teachers.teacher_id"), nullable=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=True)
    parent_id = Column(String(64), ForeignKey("parents.parent_id"), nullable=True)
    status = Column(String(32), default="active")  # active/disabled
    current_token = Column(String(128), nullable=True)  # 当前登录token
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    teacher = relationship("Teacher", back_populates="account")
    student = relationship("Student", back_populates="account")
    parent = relationship("Parent", back_populates="account")


class Class(Base):
    """班级表"""
    __tablename__ = "classes"

    class_id = Column(String(64), primary_key=True)
    teacher_id = Column(String(64), ForeignKey("teachers.teacher_id"), nullable=True)  # 改nullable=True，保留作为班主任标识
    name = Column(String(128), nullable=False)
    student_count = Column(Integer, default=0)
    grade = Column(String(32), nullable=False)  # 年级名称，如"高一"
    subject = Column(String(32), default="化学")
    grade_id = Column(String(64), ForeignKey("grades.grade_id"), nullable=True)  # 年级外键
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    teacher = relationship("Teacher", back_populates="classes")
    grade_rel = relationship("Grade", back_populates="classes")  # 重命名避免与grade列冲突
    students = relationship("Student", back_populates="student_class")
    exam_records = relationship("ExamRecord", back_populates="exam_class")
    teacher_subjects = relationship("TeacherClassSubject", back_populates="class_obj")


class ExamRecord(Base):
    """考试/练习记录表"""
    __tablename__ = "exam_records"

    record_id = Column(String(64), primary_key=True)
    class_id = Column(String(64), ForeignKey("classes.class_id"), nullable=False)
    type = Column(Enum(RecordType), default=RecordType.EXAM)
    name = Column(String(256), nullable=False)  # e.g. "高二上月考化学"
    question_stats = Column(JSON, nullable=True)  # 错题统计数据
    avg_score = Column(Float, nullable=True)
    total_students = Column(Integer, default=0)
    present_students = Column(Integer, default=0)  # 实际参考人数
    source = Column(Enum(QuestionSource), default=QuestionSource.AI_GENERATED)
    exam_date = Column(DateTime, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    exam_class = relationship("Class", back_populates="exam_records")
    questions = relationship("Question", back_populates="exam_record")


class Question(Base):
    """题目表（AI生成+手动选题）"""
    __tablename__ = "questions"

    question_id = Column(String(64), primary_key=True)
    record_id = Column(String(64), ForeignKey("exam_records.record_id"), nullable=True)
    content = Column(Text, nullable=False)  # 题目正文
    options = Column(JSON, nullable=True)  # 选项列表 ["A. xxx", "B. xxx", ...]
    answer = Column(String(256), nullable=True)  # 参考答案
    analysis = Column(Text, nullable=True)  # 题目解析
    knowledge_points = Column(JSON, nullable=True)  # 知识点标签列表
    difficulty = Column(Enum(Difficulty), default=Difficulty.MEDIUM)
    source = Column(Enum(QuestionSource), default=QuestionSource.AI_GENERATED)
    source_exam = Column(String(256), nullable=True)  # 手动选题来源: "2024年全国卷T15"
    audit_status = Column(Enum(AuditStatus), default=AuditStatus.PASSED)
    audit_report = Column(JSON, nullable=True)  # 三维审核报告内容
    historical_matches = Column(JSON, nullable=True)  # 历年真题关联列表
    # 审核维度 (用于F2安全审核)
    coefficient_correct = Column(Boolean, default=True)  # 系数配平
    condition_correct = Column(Boolean, default=True)  # 反应条件
    product_correct = Column(Boolean, default=True)  # 产物正确性
    structure_correct = Column(Boolean, default=True)  # 分子结构
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    exam_record = relationship("ExamRecord", back_populates="questions")
    student_answers = relationship("StudentAnswer", back_populates="question")


class BarrierConfig(Base):
    """障碍诊断配置表"""
    __tablename__ = "barrier_configs"

    config_id = Column(String(64), primary_key=True)
    teacher_id = Column(String(64), ForeignKey("teachers.teacher_id"), nullable=False)
    # 各障碍类型触发阈值
    concept_threshold = Column(Integer, default=3)  # 概念理解型：连续错误N次触发
    reading_threshold = Column(Integer, default=2)  # 审题障碍型：连续错误N次触发
    expression_threshold = Column(Integer, default=3)  # 表述障碍型：连续错误N次触发
    mastery_threshold = Column(Integer, default=3)  # 掌握标准：连续答对N次
    auto_sync_to_student = Column(Boolean, default=False)  # 诊断结论是否自动同步学生端
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    teacher = relationship("Teacher", back_populates="barrier_configs")


class StudentAnswer(Base):
    """学生作答记录表（用于障碍类型诊断）"""
    __tablename__ = "student_answers"

    answer_id = Column(String(64), primary_key=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    question_id = Column(String(64), ForeignKey("questions.question_id"), nullable=False)
    exam_record_id = Column(String(64), ForeignKey("exam_records.record_id"), nullable=True)

    student_answer = Column(String(256), nullable=True)  # 学生作答内容
    is_correct = Column(Boolean, nullable=False)
    barrier_type = Column(Enum(BarrierType), nullable=True)  # 判定障碍类型

    # 连续错误/正确计数（用于触发障碍诊断）
    consecutive_errors = Column(Integer, default=0)
    consecutive_correct = Column(Integer, default=0)

    answered_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    student = relationship("Student")
    question = relationship("Question")


class KnowledgePoint(Base):
    """知识点表（化学知识图谱）"""
    __tablename__ = "knowledge_points"

    kp_id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)  # e.g. "盐类水解"
    category = Column(String(128), nullable=True)  # e.g. "电解质溶液"
    description = Column(Text, nullable=True)
    # PubChem关联CID
    pubchem_cid = Column(String(64), nullable=True)
    # 关联题目数
    question_count = Column(Integer, default=0)
    # 错误率 (动态计算)
    error_rate = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HistoricalExam(Base):
    """历年真题表"""
    __tablename__ = "historical_exams"

    exam_id = Column(String(64), primary_key=True)
    source = Column(String(64), nullable=False)  # e.g. "全国卷2024"
    year = Column(Integer, nullable=False)
    question_number = Column(String(16), nullable=False)  # e.g. "T15"
    knowledge_points = Column(JSON, nullable=True)  # 知识点列表
    difficulty = Column(Enum(Difficulty), default=Difficulty.MEDIUM)
    discrimination = Column(Float, nullable=True)  # 区分度 0-1
    content = Column(Text, nullable=False)  # 题目内容
    answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionSet(Base):
    """真题集表（用户自定义收藏集）"""
    __tablename__ = "question_sets"

    set_id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)  # 真题集名称
    teacher_id = Column(String(64), nullable=True)  # 创建者教师ID
    region = Column(String(64), nullable=True)  # 来源地区，如"全国卷"
    year = Column(Integer, nullable=True)  # 年份
    source = Column(String(64), nullable=True)  # 来源说明
    description = Column(Text, nullable=True)  # 描述
    question_count = Column(Integer, default=0)  # 题目数量
    is_system = Column(Boolean, default=False)  # 是否系统预设
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    questions = relationship("QuestionSetItem", back_populates="question_set")


class QuestionSetItem(Base):
    """真题集包含的题目关联表"""
    __tablename__ = "question_set_items"

    item_id = Column(String(64), primary_key=True)
    set_id = Column(String(64), ForeignKey("question_sets.set_id"), nullable=False)
    question_id = Column(String(64), ForeignKey("questions.question_id"), nullable=False)
    sort_order = Column(Integer, default=0)  # 排序顺序
    added_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    question_set = relationship("QuestionSet", back_populates="questions")
    question = relationship("Question")


# ==================== 新增模型（Phase 1） ====================

class School(Base):
    """学校表"""
    __tablename__ = "schools"

    school_id = Column(String(64), primary_key=True)
    name = Column(String(100), nullable=False)
    region = Column(String(200), nullable=True)
    address = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    current_term = Column(String(50), nullable=True)
    subjects = Column(JSON, nullable=True)  # ["语文","数学","英语","化学",...]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    grades = relationship("Grade", back_populates="school")
    teachers = relationship("Teacher", back_populates="school")


class Grade(Base):
    """年级表"""
    __tablename__ = "grades"

    grade_id = Column(String(64), primary_key=True)
    school_id = Column(String(64), ForeignKey("schools.school_id"), nullable=True)
    name = Column(String(50), nullable=False)  # "高一"
    year = Column(Integer, nullable=False)  # 2025
    status = Column(Integer, default=1)  # 1:在读 0:已毕业
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    school = relationship("School", back_populates="grades")
    classes = relationship("Class", back_populates="grade_rel")


class TeacherClassSubject(Base):
    """教师-班级-科目关联表（多对多）"""
    __tablename__ = "teacher_class_subject"

    id = Column(String(64), primary_key=True)
    teacher_id = Column(String(64), ForeignKey("teachers.teacher_id"), nullable=False)
    class_id = Column(String(64), ForeignKey("classes.class_id"), nullable=False)
    subject = Column(String(50), nullable=False)
    is_class_teacher = Column(Boolean, default=False)  # 是否班主任
    assigned_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    teacher = relationship("Teacher", back_populates="teacher_subjects")
    class_obj = relationship("Class", back_populates="teacher_subjects")


class TeacherApplication(Base):
    """教师入驻申请表"""
    __tablename__ = "teacher_applications"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=False)
    school = Column(String(200), nullable=True)
    subject = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")  # pending/approved/rejected
    reviewer_id = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=True)
    action = Column(String(50), nullable=False)  # create/update/delete/login
    target_type = Column(String(50), nullable=True)  # student/teacher/class/grade
    target_id = Column(String(64), nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Parent(Base):
    """家长表"""
    __tablename__ = "parents"

    parent_id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=True)
    email = Column(String(128), nullable=True)
    password_hash = Column(String(256), nullable=False)
    status = Column(String(32), default="active")  # active/disabled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    bindings = relationship("StudentParentBinding", back_populates="parent")
    notifications = relationship("ParentNotification", back_populates="parent")
    account = relationship("Account", back_populates="parent", uselist=False)


class StudentParentBinding(Base):
    """亲子绑定表"""
    __tablename__ = "student_parent_bindings"

    binding_id = Column(String(64), primary_key=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    parent_id = Column(String(64), ForeignKey("parents.parent_id"), nullable=False)
    relation = Column(String(32), default="家长")  # 父亲/母亲/其他
    status = Column(String(32), default="active")  # pending/active/inactive
    bind_code = Column(String(64), nullable=False)  # 绑定验证码
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    student = relationship("Student", back_populates="parent_bindings")
    parent = relationship("Parent", back_populates="bindings")


class ParentNotification(Base):
    """家长通知记录表"""
    __tablename__ = "parent_notifications"

    notification_id = Column(String(64), primary_key=True)
    parent_id = Column(String(64), ForeignKey("parents.parent_id"), nullable=False)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    type = Column(String(32), nullable=False)  # weekly_report/score_alert/learning_plan/reminder/daily_report
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    parent = relationship("Parent", back_populates="notifications")
    student = relationship("Student")


class UploadSession(Base):
    """OCR 上传会话状态机"""
    __tablename__ = "upload_sessions"

    id = Column(String(64), primary_key=True)
    file_data = Column("file_data", LargeBinary, nullable=True)
    file_name = Column(String(512), nullable=True)
    mime_type = Column(String(128), nullable=True)
    status = Column(String(32), default="uploaded", index=True)
    preview_text = Column(Text, nullable=True)
    formula_result = Column(Text, nullable=True)
    detected_type = Column(String(32), nullable=True)
    baidu_task_id = Column(String(128), nullable=True)
    page_count = Column(Integer, default=0)
    pages_completed = Column(Integer, default=0)
    result_json = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    degraded = Column(Boolean, default=False)
    version = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StudentSubmission(Base):
    """学生作答记录 — 关联考试和班级"""
    __tablename__ = "student_submissions"

    submission_id = Column(String(64), primary_key=True)
    exam_id = Column(String(64), ForeignKey("exam_records.record_id"), nullable=True)
    class_id = Column(String(64), nullable=True, index=True)
    student_name = Column(String(128), nullable=True)
    original_image = Column(String(512), nullable=True)
    graded_image = Column(String(512), nullable=True)
    answers_json = Column(Text, nullable=True)
    total_score = Column(Integer, default=0)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    graded_at = Column(DateTime, nullable=True)


# 数据库初始化函数
_default_engine = None
_default_session_factory = None

def get_engine(database_url: str = "sqlite:///./chemai.db"):
    """获取数据库引擎（单例）"""
    global _default_engine
    if _default_engine is None:
        _default_engine = create_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        )
        # Enable WAL mode for better concurrency
        if "sqlite" in database_url:
            from sqlalchemy import event
            @event.listens_for(_default_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()
    return _default_engine

def get_session_factory(database_url: str = "sqlite:///./chemai.db"):
    """获取会话工厂（单例）"""
    global _default_session_factory
    if _default_session_factory is None:
        engine = get_engine(database_url)
        _default_session_factory = sessionmaker(bind=engine)
    return _default_session_factory

def get_db():
    """获取数据库会话（用于FastAPI依赖注入）"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LearningPlanHistory(Base):
    """学习计划历史记录"""
    __tablename__ = "learning_plan_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    plan_title = Column(String(256), nullable=False)
    plan_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db(database_url: str = "sqlite:///./chemai.db"):
    """初始化数据库（创建所有表）"""
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    return engine

# 为了兼容旧代码，也导出默认engine
engine = get_engine()
