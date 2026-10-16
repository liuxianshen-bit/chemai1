"""Randomize student demo data — barrier types, exercise counts, answer history.

Usage:
  python tools/randomize_students.py          # skip students with existing answers
  python tools/randomize_students.py --force  # overwrite all students
"""

import sys, os, random, json, hashlib, argparse
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.database import get_db, Student, StudentAnswer
from sqlalchemy import text

KPS = ['盐类水解','离子反应','氧化还原','化学平衡','元素周期律','物质的量','有机化学','电化学','化学实验','反应速率']
PASSWORD = hashlib.sha256('123456'.encode()).hexdigest()

def random_barrier():
    """Generate random barrier distribution summing to 1.0."""
    a, b, c = random.random(), random.random(), random.random()
    total = a + b + c
    vals = [round(a/total, 2), round(b/total, 2), round(c/total, 2)]
    # Ensure sum = 1.0
    vals[2] = round(1.0 - vals[0] - vals[1], 2)
    random.shuffle(vals)
    return {"concept": vals[0], "reading": vals[1], "expression": vals[2]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Overwrite students with existing answers')
    args = parser.parse_args()

    db = next(get_db())
    students = db.query(Student).all()
    skipped = 0
    updated = 0

    PRESERVED = {'202610201'}  # 李雨萱 — 演示用, 不随机化

    for s in students:
        if s.student_id in PRESERVED:
            skipped += 1; continue
        existing = db.query(StudentAnswer).filter(StudentAnswer.student_id == s.student_id).count()
        if existing > 0 and not args.force:
            skipped += 1
            continue

        # Clear old answers for this student
        db.execute(text('DELETE FROM student_answers WHERE student_id=:sid'), {'sid': s.student_id})

        # Random barrier
        bt = random_barrier()
        s.barrier_type = json.dumps(bt)
        s.exercises_completed = random.randint(0, 50)

        # Random answer history (7-30 days)
        days = random.randint(7, 30)
        accuracy = random.uniform(0.40, 0.95)
        for doff in range(days, 0, -1):
            day = datetime.utcnow() - timedelta(days=doff)
            q_count = random.randint(2, 6)
            for qn in range(q_count):
                kp = random.sample(KPS, random.randint(1, 2))
                ok = random.random() < accuracy
                qid = f'q_rand_{s.student_id}_{doff}_{qn}'
                db.execute(text('''INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status)
                    VALUES (:q, 'rec_rand', :c, :o, :a, :al, :k, :d, 'manual', 'passed')'''), {
                    'q': qid, 'c': f'[{kp[0]}] 模拟题 #{doff}-{qn}', 'o': json.dumps(['A.选项','B.选项','C.选项','D.选项']),
                    'a': 'A' if ok else 'B', 'al': '正确' if ok else '需要加强', 'k': json.dumps(kp),
                    'd': random.choice(['easy','medium','medium','medium','hard']),
                })
                db.execute(text('''INSERT OR IGNORE INTO student_answers (answer_id, student_id, question_id, exam_record_id, student_answer, is_correct, answered_at)
                    VALUES (:aid, :sid, :qid, 'rec_rand', :an, :ok, :at)'''), {
                    'aid': f'a_rand_{s.student_id}_{doff}_{qn}', 'sid': s.student_id, 'qid': qid,
                    'an': 'A' if ok else 'B', 'ok': ok,
                    'at': day + timedelta(hours=random.randint(8, 21), minutes=random.randint(0, 59)),
                })
        updated += 1
        if updated % 10 == 0:
            db.commit()
            print(f'  {updated}/{len(students)} students done...')

    db.commit()
    db.close()
    print(f'Done: {updated} updated, {skipped} skipped (had existing answers)')

if __name__ == '__main__':
    main()
