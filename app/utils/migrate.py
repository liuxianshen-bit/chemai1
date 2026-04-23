"""
数据库迁移脚本
处理新增表和表结构变更

使用方式:
    python -m app.utils.migrate
"""
import os
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from sqlalchemy import text, inspect
from app.models.database import get_engine, get_session_factory


def get_existing_tables(engine):
    """获取现有表列表（兼容不同SQLAlchemy版本）"""
    inspector = inspect(engine)
    return inspector.get_table_names()


def migrate():
    """执行数据库迁移"""
    engine = get_engine()
    session_factory = get_session_factory()
    session = session_factory()

    print("=" * 50)
    print("ChemAI Database Migration")
    print("=" * 50)

    try:
        # 获取现有表列表
        existing_tables = get_existing_tables(engine)
        print(f"\nExisting tables: {existing_tables}")

        # 检查是否需要迁移
        if 'schools' in existing_tables:
            print("\n[OK] schools table exists, skip")
        else:
            create_schools_table(engine)
            print("[OK] schools table created")

        if 'grades' in existing_tables:
            print("[OK] grades table exists, skip")
        else:
            create_grades_table(engine)
            print("[OK] grades table created")

        if 'teacher_class_subject' in existing_tables:
            print("[OK] teacher_class_subject table exists, skip")
        else:
            create_teacher_class_subject_table(engine)
            print("[OK] teacher_class_subject table created")

        if 'teacher_applications' in existing_tables:
            print("[OK] teacher_applications table exists, skip")
        else:
            create_teacher_applications_table(engine)
            print("[OK] teacher_applications table created")

        if 'operation_logs' in existing_tables:
            print("[OK] operation_logs table exists, skip")
        else:
            create_operation_logs_table(engine)
            print("[OK] operation_logs table created")

        # 处理现有表的结构变更
        migrate_classes_table(engine)
        migrate_teachers_table(engine)

        print("\n" + "=" * 50)
        print("Migration completed!")
        print("=" * 50)

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def create_schools_table(engine):
    """创建学校表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS schools (
            school_id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            region VARCHAR(200),
            address VARCHAR(255),
            phone VARCHAR(20),
            current_term VARCHAR(50),
            subjects JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def create_grades_table(engine):
    """创建年级表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS grades (
            grade_id VARCHAR(64) PRIMARY KEY,
            school_id VARCHAR(64),
            name VARCHAR(50) NOT NULL,
            year INTEGER NOT NULL,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (school_id) REFERENCES schools(school_id)
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def create_teacher_class_subject_table(engine):
    """创建教师-班级-科目关联表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS teacher_class_subject (
            id VARCHAR(64) PRIMARY KEY,
            teacher_id VARCHAR(64) NOT NULL,
            class_id VARCHAR(64) NOT NULL,
            subject VARCHAR(50) NOT NULL,
            is_class_teacher BOOLEAN DEFAULT 0,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id),
            FOREIGN KEY (class_id) REFERENCES classes(class_id),
            UNIQUE (teacher_id, class_id, subject)
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def create_teacher_applications_table(engine):
    """创建教师入驻申请表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS teacher_applications (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(128) NOT NULL,
            phone VARCHAR(32) NOT NULL,
            school VARCHAR(200),
            subject VARCHAR(50),
            status VARCHAR(20) DEFAULT 'pending',
            reviewer_id VARCHAR(64),
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def create_operation_logs_table(engine):
    """创建操作日志表"""
    sql = text("""
        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(64),
            action VARCHAR(50) NOT NULL,
            target_type VARCHAR(50),
            target_id VARCHAR(64),
            detail JSON,
            ip_address VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def migrate_classes_table(engine):
    """迁移classes表：添加grade_id列"""
    with engine.connect() as conn:
        # 检查grade_id列是否存在
        result = conn.execute(text("PRAGMA table_info(classes)"))
        columns = [row[1] for row in result.fetchall()]

        if 'grade_id' not in columns:
            # SQLite不支持直接ADD FOREIGN KEY，需要分步
            # 1. 添加grade_id列
            conn.execute(text("ALTER TABLE classes ADD COLUMN grade_id VARCHAR(64)"))
            conn.commit()
            print("[OK] classes.grade_id column added")
        else:
            print("[OK] classes.grade_id column exists, skip")

        # 检查grade列是否需要保留（保留作为年级名称）
        if 'grade' not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN grade VARCHAR(32) DEFAULT '高一'"))
            conn.commit()
            print("[OK] classes.grade column added")
        else:
            print("[OK] classes.grade column exists, skip")


def migrate_teachers_table(engine):
    """迁移teachers表：添加role列"""
    with engine.connect() as conn:
        # 检查role列是否存在
        result = conn.execute(text("PRAGMA table_info(teachers)"))
        columns = [row[1] for row in result.fetchall()]

        if 'role' not in columns:
            conn.execute(text("ALTER TABLE teachers ADD COLUMN role VARCHAR(32) DEFAULT 'teacher'"))
            conn.commit()
            print("[OK] teachers.role column added")
        else:
            print("[OK] teachers.role column exists, skip")


if __name__ == "__main__":
    migrate()
