"""Generate multi-exam data for all students — enabling score trend chart."""
import sqlite3, json, random, uuid
from datetime import datetime, timedelta

random.seed(42)
DB = "chemai.db"
conn = sqlite3.connect(DB)

EXAMS = [
    ("gen_exam_1", "第一周 基础概念",     "2026-06-10", 0.55, ["物质的量", "元素周期律"]),
    ("gen_exam_2", "第二周 化学反应",     "2026-06-17", 0.62, ["氧化还原", "离子反应"]),
    ("gen_exam_3", "第三周 化学平衡",     "2026-06-24", 0.68, ["化学平衡", "反应速率"]),
    ("gen_exam_4", "第四周 盐类水解",     "2026-07-01", 0.74, ["盐类水解", "电离平衡"]),
]

CLASSES = ["class_2025_1", "class_2025_2"]

# Index all questions by knowledge points
all_qs = {}
for r in conn.execute("SELECT question_id, knowledge_points FROM questions"):
    kps = json.loads(r[1]) if isinstance(r[1], str) else (r[1] or [])
    all_qs[r[0]] = kps

def pick_qs(topics, n=12):
    scored = [(qid, sum(1 for t in topics if any(t in kp for kp in kps))) for qid, kps in all_qs.items()]
    scored.sort(key=lambda x: -x[1])
    picked = [s[0] for s in scored if s[1] > 0][:n]
    if len(picked) < n:
        rest = [qid for qid in all_qs if qid not in picked]
        picked += random.sample(rest, min(n - len(picked), len(rest)))
    return picked

uid = 0
for cls_id in CLASSES:
    sts = conn.execute("SELECT student_id FROM students WHERE class_id = ?", (cls_id,)).fetchall()
    for eid, ename, edate, eavg, etopics in EXAMS:
        exist = conn.execute("SELECT 1 FROM exam_records WHERE record_id = ?", (eid + "_" + cls_id,)).fetchone()
        if exist:
            continue
        qids = pick_qs(etopics, 12)
        kps = set(); [kps.update(all_qs.get(q, [])) for q in qids]
        conn.execute(
            "INSERT INTO exam_records (record_id, class_id, type, name, question_stats, avg_score, total_students, present_students, source, exam_date, created_at) VALUES (?,?,'PRACTICE',?,?,?,?,?,'generated',?,?)",
            (eid + "_" + cls_id, cls_id, ename, json.dumps({"question_count":len(qids),"knowledge_points":list(kps)}, ensure_ascii=False),
             eavg, len(sts), len(sts), 'ai_generated', edate, datetime.now().isoformat()))

        for (sid,) in sts:
            acc = min(0.98, max(0.2, eavg + random.uniform(-0.15, 0.15)))
            for qi, qid in enumerate(qids):
                uid += 1
                ok = 1 if random.random() < acc else 0
                bt = "" if ok else random.choice(["CONCEPT","READING","EXPRESSION"])
                ts = (datetime.strptime(edate, "%Y-%m-%d") + timedelta(hours=qi*0.2)).isoformat()
                conn.execute(
                    "INSERT INTO student_answers (answer_id, student_id, question_id, exam_record_id, student_answer, is_correct, barrier_type, answered_at) VALUES (?,?,?,?,?,?,?,?)",
                    (f"g_{uid}", sid, qid, eid + "_" + cls_id, "A" if ok else random.choice(["B","C","D"]), ok, bt if bt else None, ts))

conn.commit()
print(f"Inserted {uid} answers across {len(CLASSES)*len(EXAMS)} exams")

# Update barrier_type + exercises_completed
for (sid,) in conn.execute("SELECT student_id FROM students"):
    bc = {"CONCEPT":0,"READING":0,"EXPRESSION":0}
    for (bt,) in conn.execute("SELECT barrier_type FROM student_answers WHERE student_id=? AND is_correct=0 AND barrier_type IS NOT NULL", (sid,)):
        if bt in bc: bc[bt] += 1
    tw = sum(bc.values()) or 1
    corr = conn.execute("SELECT COUNT(*) FROM student_answers WHERE student_id=? AND is_correct=1", (sid,)).fetchone()[0]
    conn.execute("UPDATE students SET barrier_type=?, exercises_completed=? WHERE student_id=?",
                 (json.dumps({k: round(v/tw,2) for k,v in bc.items()}, ensure_ascii=False), corr, sid))

conn.commit()

# Verify
for r in conn.execute("SELECT COUNT(DISTINCT exam_record_id), COUNT(*) FROM student_answers").fetchone():
    print(f"Total: {r[0]} exams, {r[1]} answers")
for r in conn.execute("SELECT student_id, name, exercises_completed FROM students WHERE student_id='202610201'").fetchone():
    print(f"  李雨萱: {r[2]} questions completed")
conn.close()
print("Done.")
