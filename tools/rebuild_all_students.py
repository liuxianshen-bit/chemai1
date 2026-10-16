"""Rebuild ALL student data with diverse, realistic distributions.

Preserves: 李雨萱 (202610201), 陈思雨 (202610101, formerly 李雨萱)
Creates: diverse barriers, exercise counts, answer histories for 66 students.

Usage: python tools/rebuild_all_students.py
"""
import sys, os, json, random
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.database import get_db
from sqlalchemy import text

PRESERVED = {'202610201'}  # 李雨萱 demo
KPS_ALL = ['盐类水解','离子反应','氧化还原','化学平衡','元素周期律','物质的量','有机化学','电化学','化学实验','反应速率']

# 共享10道真实题 (复用李雨萱题库)
SHARED_QUESTIONS = [
    {"id": "demo_q_00", "diff": "easy",   "kps": ["盐类水解"]},
    {"id": "demo_q_01", "diff": "medium", "kps": ["盐类水解","化学平衡"]},
    {"id": "demo_q_02", "diff": "medium", "kps": ["离子反应"]},
    {"id": "demo_q_03", "diff": "hard",   "kps": ["氧化还原"]},
    {"id": "demo_q_04", "diff": "easy",   "kps": ["化学平衡"]},
    {"id": "demo_q_05", "diff": "medium", "kps": ["元素周期律"]},
    {"id": "demo_q_06", "diff": "easy",   "kps": ["物质的量"]},
    {"id": "demo_q_07", "diff": "easy",   "kps": ["有机化学"]},
    {"id": "demo_q_08", "diff": "medium", "kps": ["电化学"]},
    {"id": "demo_q_09", "diff": "hard",   "kps": ["化学平衡","物质的量"]},
]

def random_barrier():
    """Three random values that sum to 1.0, with clear variance."""
    a, b, c = random.random(), random.random(), random.random()
    total = a + b + c
    vals = [round(a/total, 2), round(b/total, 2), round(c/total, 2)]
    vals[2] = round(1.0 - vals[0] - vals[1], 2)
    random.shuffle(vals)
    return {"concept": vals[0], "reading": vals[1], "expression": vals[2]}

def main():
    db = next(get_db())
    students = db.execute(text("SELECT student_id, name FROM students ORDER BY student_id")).fetchall()

    # Clear old answers (except preserved students)
    for s in students:
        if s[0] in PRESERVED: continue
        db.execute(text("DELETE FROM student_answers WHERE student_id=:s"), {"s": s[0]})

    # Create exam records for both classes
    for cls_id, cls_name in [("class_2025_1", "高一(1)班"), ("class_2025_2", "高一(2)班")]:
        rid = f"class_exam_{cls_id[-1]}"
        db.execute(text("DELETE FROM exam_records WHERE record_id=:r"), {"r": rid})
        db.execute(text("""INSERT INTO exam_records(record_id, class_id, name, type, total_students, present_students, exam_date, question_stats)
            VALUES (:r, :c, :n, 'PRACTICE', 34, 34, :d, :s)"""), {
            "r": rid, "c": cls_id, "n": f"{cls_name} 化学综合练习",
            "d": datetime.utcnow() - timedelta(days=2),
            "s": json.dumps({"published": True, "question_count": 10, "knowledge_points": KPS_ALL[:8]})
        })

    # Copy 10 real questions to both exam records
    for cls_id in ["class_2025_1", "class_2025_2"]:
        rid = f"class_exam_{cls_id[-1]}"
        for sq in SHARED_QUESTIONS:
            src = sq["id"]
            dst = f"{rid}_{sq['id'].split('_')[-1]}"
            db.execute(text("""INSERT OR REPLACE INTO questions(question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status)
                SELECT :dst, :rid, content, options, answer, analysis, knowledge_points, difficulty, 'manual', 'passed'
                FROM questions WHERE question_id = :src"""), {"dst": dst, "rid": rid, "src": src})

    db.commit()

    # Process each student
    concept_dom = reading_dom = expression_dom = 0
    total_answers = 0
    attention_count = 0

    for s in students:
        sid, sname = s[0], s[1]
        if sid in PRESERVED:
            continue

        # Random barrier
        bt = random_barrier()
        dominant = max(bt.items(), key=lambda x: x[1])[0]
        if dominant == 'concept': concept_dom += 1
        elif dominant == 'reading': reading_dom += 1
        else: expression_dom += 1

        # Random exercise count (normal-like distribution via sum of dice)
        ex_count = sum(random.randint(1, 6) for _ in range(6)) + random.randint(0, 10)  # 6-46, mean ~26
        ex_count = min(ex_count, 45)

        # Accuracy bias by dominant barrier:
        # concept-dominant: worse on easy questions (surprising but realistic)
        # reading-dominant: worse on medium questions
        # expression-dominant: worse on hard questions
        base_accuracy = random.uniform(0.50, 0.90)

        class_suffix = sid[5]
        cls_id = f"class_2025_{class_suffix}" if class_suffix in ('1','2') else "class_2025_1"
        exam_rid = f"class_exam_{cls_id[-1]}"

        # Generate answers
        answer_count = min(random.randint(10, 30), 30)
        correct = 0
        for _ in range(answer_count):
            sq = random.choice(SHARED_QUESTIONS)
            qid = f"{exam_rid}_{sq['id'].split('_')[-1]}"

            # Accuracy varies by question difficulty and student's dominant barrier
            diff_factor = {"easy": 1.0, "medium": 0.85, "hard": 0.65}
            q_acc = base_accuracy * diff_factor.get(sq["diff"], 0.8)
            # Dominant barrier reduces accuracy slightly on matching difficulty
            if dominant == 'concept' and sq['diff'] == 'easy': q_acc *= 0.85
            elif dominant == 'reading' and sq['diff'] == 'medium': q_acc *= 0.85
            elif dominant == 'expression' and sq['diff'] == 'hard': q_acc *= 0.85

            ok = random.random() < q_acc
            if ok: correct += 1

            day_offset = random.randint(0, 13)
            day = datetime.utcnow() - timedelta(days=day_offset)
            aid = f"rb_{sid}_{day_offset}_{random.randint(0,9999)}"
            db.execute(text("""INSERT INTO student_answers(answer_id, student_id, question_id, exam_record_id, student_answer, is_correct, answered_at)
                VALUES (:a, :s, :q, :r, :an, :ok, :at)"""), {
                "a": aid, "s": sid, "q": qid, "r": exam_rid,
                "an": "A" if ok else "B", "ok": ok,
                "at": day + timedelta(hours=random.randint(8, 22), minutes=random.randint(0, 59)),
            })

        # Update student record
        db.execute(text("""UPDATE students SET barrier_type=:bt, exercises_completed=:ex, last_exercise_at=:la
            WHERE student_id=:s"""), {
            "bt": json.dumps(bt), "ex": answer_count,
            "la": datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
            "s": sid,
        })

        max_val = max(bt.values())
        if max_val > 0.6: attention_count += 1
        total_answers += answer_count

        if (concept_dom + reading_dom + expression_dom) % 10 == 0:
            db.commit()
            print(f"  {concept_dom + reading_dom + expression_dom} students done...")

    db.commit()

    total_students = len(students) - len(PRESERVED)
    print(f"\nDone: {total_students} students updated")
    print(f"  concept dominant: {concept_dom}")
    print(f"  reading dominant: {reading_dom}")
    print(f"  expression dominant: {expression_dom}")
    print(f"  need attention (>0.6): {attention_count}")
    print(f"  total answers generated: {total_answers}")

    # Verify
    sample = db.execute(text("SELECT student_id, name, barrier_type, exercises_completed FROM students ORDER BY RANDOM() LIMIT 5")).fetchall()
    print(f"\nSample data:")
    for r in sample:
        bt = json.loads(r[2]) if isinstance(r[2], str) else r[2]
        domin = max(bt.items(), key=lambda x: x[1])[0] if bt else "?"
        ac = db.execute(text("SELECT COUNT(*) FROM student_answers WHERE student_id=:s"), {"s": r[0]}).fetchone()[0]
        print(f"  {r[1]:6s} | {domin:10s} | barrier={bt} | ex={r[3]} | answers={ac}")

    db.close()

if __name__ == '__main__':
    main()
