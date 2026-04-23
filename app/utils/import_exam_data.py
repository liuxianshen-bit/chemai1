"""
导入历史考试数据 - 补充版
为邵阳县第一中学添加更多考试记录
"""
import json
import random
from datetime import datetime
from app.models.database import get_db, ExamRecord, Question, StudentAnswer, Student, Class
from app.models.database import QuestionSource, Difficulty, AuditStatus, BarrierType

# 额外补充的考试配置
EXTRA_EXAM_CONFIG = [
    {
        "name": "高一化学期中考试",
        "exam_date": "2025-11-30",
        "class_id": "class_2025_2",
        "source_files": [
            "data/exam_questions/hunan_2024_full.json",
            "data/exam_questions/hunan_2023_full.json",
            "data/exam_questions/national_2019_full.json",
        ],
    },
    {
        "name": "高一化学期末考试",
        "exam_date": "2025-12-28",
        "class_id": "class_2025_2",
        "source_files": [
            "data/exam_questions/hunan_2022_full.json",
            "data/exam_questions/national_2020_full.json",
            "data/exam_questions/national_2018_full.json",
            "data/exam_questions/national_2017_full.json",
        ],
    },
    {
        "name": "高一化学月考（三）",
        "exam_date": "2025-12-20",
        "class_id": "class_2025_2",
        "source_files": [
            "data/exam_questions/national_2023_full.json",
            "data/exam_questions/national_2022_full.json",
        ],
    },
    {
        "name": "高一化学月考（四）",
        "exam_date": "2026-01-10",
        "class_id": "class_2025_2",
        "source_files": [
            "data/exam_questions/hunan_2021_full.json",
            "data/exam_questions/national_2016_full.json",
            "data/exam_questions/national_2015_full.json",
        ],
    },
]

# 障碍类型分布
BARRIER_WEIGHTS = {
    BarrierType.CONCEPT: 0.25,
    BarrierType.READING: 0.35,
    BarrierType.EXPRESSION: 0.20,
    None: 0.20
}


def load_questions_from_files(file_paths):
    all_questions = []
    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                questions = data.get('questions', [])
                all_questions.extend(questions)
        except Exception as e:
            print(f"  加载文件失败 {file_path}: {e}")
    return all_questions


def difficulty_str_to_enum(difficulty_str):
    mapping = {
        'easy': Difficulty.EASY,
        'medium': Difficulty.MEDIUM,
        'hard': Difficulty.HARD,
        'competition': Difficulty.COMPETITION
    }
    return mapping.get(difficulty_str, Difficulty.MEDIUM)


def add_extra_exams():
    print("=" * 60)
    print("补充考试数据 - 邵阳县第一中学")
    print("=" * 60)

    db = next(get_db())
    try:
        class_2 = db.query(Class).filter(Class.class_id == "class_2025_2").first()
        if not class_2:
            print("错误: 找不到高一(2)班")
            return

        print(f"补充班级: {class_2.name} (学生数: {class_2.student_count})")

        students = db.query(Student).filter(Student.class_id == "class_2025_2").all()
        print(f"学生数: {len(students)}")

        total_questions = 0
        total_answers = 0

        for i, exam_cfg in enumerate(EXTRA_EXAM_CONFIG):
            print(f"\n[{i+1}/{len(EXTRA_EXAM_CONFIG)}] {exam_cfg['name']}")

            # 检查是否已存在
            existing = db.query(ExamRecord).filter(
                ExamRecord.name == exam_cfg['name'],
                ExamRecord.class_id == exam_cfg['class_id']
            ).first()

            if existing:
                print(f"  已存在，跳过")
                q_count = db.query(Question).filter(Question.record_id == existing.record_id).count()
                total_questions += q_count
                continue

            # 加载题目
            questions = load_questions_from_files(exam_cfg['source_files'])
            print(f"  加载题目: {len(questions)}道")

            if not questions:
                continue

            # 创建考试记录
            record_id = f"exam_extra_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i+1}"
            exam_record = ExamRecord(
                record_id=record_id,
                class_id=exam_cfg['class_id'],
                type="exam",
                name=exam_cfg['name'],
                exam_date=datetime.strptime(exam_cfg['exam_date'], '%Y-%m-%d'),
                total_students=len(students),
                source=QuestionSource.MANUAL_SELECTED
            )
            db.add(exam_record)
            db.commit()

            # 导入题目
            for j, q_data in enumerate(questions):
                question_id = f"q_{record_id}_{j+1}"
                difficulty = difficulty_str_to_enum(q_data.get('difficulty', 'medium'))

                question = Question(
                    question_id=question_id,
                    record_id=record_id,
                    content=q_data.get('content', ''),
                    options=q_data.get('options'),
                    answer=q_data.get('answer'),
                    analysis=q_data.get('analysis'),
                    knowledge_points=q_data.get('knowledge_points'),
                    difficulty=difficulty,
                    source=QuestionSource.MANUAL_SELECTED,
                    source_exam=q_data.get('source', ''),
                    audit_status=AuditStatus.PASSED
                )
                db.add(question)

                # 为每个学生生成答题记录
                for student in students:
                    if difficulty == Difficulty.EASY:
                        correct_rate = 0.85
                    elif difficulty == Difficulty.MEDIUM:
                        correct_rate = 0.70
                    else:
                        correct_rate = 0.55

                    is_correct = random.random() < correct_rate

                    if is_correct:
                        barrier_type = None
                        student_answer = q_data.get('answer')
                    else:
                        barrier_type = random.choices(
                            list(BARRIER_WEIGHTS.keys()),
                            weights=list(BARRIER_WEIGHTS.values())
                        )[0]
                        if q_data.get('options'):
                            student_answer = random.choice([opt.split('.')[0] for opt in q_data['options'] if '.' in opt])
                        else:
                            student_answer = "错误答案"

                    answer_id = f"ans_{question_id}_{student.student_id}"
                    student_answer_record = StudentAnswer(
                        answer_id=answer_id,
                        student_id=student.student_id,
                        question_id=question_id,
                        exam_record_id=record_id,
                        student_answer=student_answer,
                        is_correct=is_correct,
                        barrier_type=barrier_type,
                        consecutive_errors=random.randint(0, 3) if not is_correct else 0,
                        consecutive_correct=random.randint(0, 5) if is_correct else 0
                    )
                    db.add(student_answer_record)
                    total_answers += 1

                total_questions += 1

            db.commit()
            print(f"  完成: {len(questions)}题 x {len(students)}学生 = {len(questions)*len(students)}条记录")

        print("\n" + "=" * 60)
        print(f"补充完成! 新增 {total_questions} 题, {total_answers} 条答题记录")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n补充失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    add_extra_exams()
