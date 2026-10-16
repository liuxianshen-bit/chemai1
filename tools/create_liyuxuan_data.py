"""为李雨萱创建完整演示数据 — 练习/错题/统计/报告 全链路可用。

运行: python tools/create_liyuxuan_data.py
幂等: 已存在数据时跳过, 重启不丢。
"""

import sys, os, json, random, hashlib
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.database import get_db, Student, Account
from sqlalchemy import text

SID = '202610201'
PID = 'parent_lyx'
PW = hashlib.sha256('123456'.encode()).hexdigest()

# ── 10道真实化学题 ──
QUESTIONS = [
    {"content":"下列关于盐类水解的说法，正确的是","options":["A.NaCl溶液呈碱性","B.NH₄Cl溶液呈酸性","C.Na₂CO₃溶液呈中性","D.KNO₃溶液呈碱性"],"answer":"B","analysis":"NH₄Cl是强酸弱碱盐，NH₄⁺水解使溶液呈酸性。NaCl和KNO₃是强酸强碱盐不水解。Na₂CO₃是强碱弱酸盐，水解呈碱性。","knowledge_points":["盐类水解"],"difficulty":"easy"},
    {"content":"在FeCl₃溶液中，下列操作能使Fe³⁺水解程度增大的是","options":["A.加入少量HCl","B.加入少量NaOH","C.加入少量NaCl","D.降温"],"answer":"B","analysis":"Fe³⁺ + 3H₂O ⇌ Fe(OH)₃ + 3H⁺，加入NaOH消耗H⁺，平衡正向移动，水解程度增大。","knowledge_points":["盐类水解","化学平衡"],"difficulty":"medium"},
    {"content":"下列离子方程式书写正确的是","options":["A.铁与稀盐酸: 2Fe+6H⁺=2Fe³⁺+3H₂↑","B.碳酸钙与盐酸: CO₃²⁻+2H⁺=CO₂↑+H₂O","C.氢氧化钡与硫酸: Ba²⁺+2OH⁻+2H⁺+SO₄²⁻=BaSO₄↓+2H₂O","D.铜与硝酸银: Cu+Ag⁺=Cu²⁺+Ag"],"answer":"C","analysis":"C正确写出了离子反应。A中铁与稀盐酸生成Fe²⁺不是Fe³⁺。B中CaCO₃难溶不能拆。D电荷不守恒。","knowledge_points":["离子反应"],"difficulty":"medium"},
    {"content":"在反应2KMnO₄+16HCl=2KCl+2MnCl₂+5Cl₂↑+8H₂O中，被氧化的HCl与未被氧化的HCl的物质的量之比为","options":["A.1:5","B.5:3","C.3:5","D.5:8"],"answer":"B","analysis":"16个HCl中，10个Cl⁻被氧化为5Cl₂（化合价从-1升到0），6个Cl⁻化合价未变。被氧化:未被氧化=10:6=5:3。","knowledge_points":["氧化还原"],"difficulty":"hard"},
    {"content":"对于可逆反应2SO₂(g)+O₂(g)⇌2SO₃(g) ΔH<0，下列措施能使平衡正向移动的是","options":["A.升高温度","B.减小压强","C.通入O₂","D.加入催化剂"],"answer":"C","analysis":"增加反应物O₂浓度，平衡向正反应方向移动。ΔH<0是放热反应，升温平衡逆向移动。减小压强平衡向气体分子数增大的方向(逆向)移动。催化剂不影响平衡。","knowledge_points":["化学平衡"],"difficulty":"easy"},
    {"content":"短周期元素X、Y、Z的原子序数依次增大，X原子的最外层电子数是次外层的2倍，Y的氧化物有两性，Z的原子半径在同周期中最小。下列说法正确的是","options":["A.X是碳元素","B.Y是铝元素","C.Z的氢化物最稳定","D.原子半径X>Y>Z"],"answer":"B","analysis":"X最外层=次外层×2 → X是碳(2,4)。Y的氧化物有两性 → Y是铝。Z同周期半径最小 → Z是氯(第三周期)。Y是Al正确。","knowledge_points":["元素周期律"],"difficulty":"medium"},
    {"content":"标准状况下，22.4L CO₂的物质的量是","options":["A.0.5mol","B.1mol","C.2mol","D.22.4mol"],"answer":"B","analysis":"标准状况下，气体摩尔体积为22.4L/mol。n=V/Vm=22.4/22.4=1mol。","knowledge_points":["物质的量"],"difficulty":"easy"},
    {"content":"下列有机物中，能与NaHCO₃溶液反应放出CO₂的是","options":["A.乙醇","B.乙酸","C.乙酸乙酯","D.乙醛"],"answer":"B","analysis":"羧酸(乙酸CH₃COOH)酸性强于碳酸，能与NaHCO₃反应生成CO₂。醇、酯、醛不与NaHCO₃反应。","knowledge_points":["有机化学"],"difficulty":"easy"},
    {"content":"在电解饱和食盐水的实验中，阳极产生的气体是","options":["A.H₂","B.O₂","C.Cl₂","D.HCl"],"answer":"C","analysis":"电解饱和食盐水: 阳极2Cl⁻-2e⁻=Cl₂↑, 阴极2H⁺+2e⁻=H₂↑。阳极产生氯气。","knowledge_points":["电化学"],"difficulty":"medium"},
    {"content":"对于反应N₂(g)+3H₂(g)⇌2NH₃(g)，在某温度下达到平衡时，[N₂]=2mol/L，[H₂]=3mol/L，[NH₃]=4mol/L，则该温度下的平衡常数K为","options":["A.0.15","B.0.3","C.0.44","D.0.89"],"answer":"B","analysis":"K=[NH₃]²/([N₂][H₂]³)=4²/(2×3³)=16/(2×27)=16/54≈0.30。","knowledge_points":["化学平衡","物质的量"],"difficulty":"hard"},
]

def main():
    db = next(get_db())

    # ── 检查是否已初始化 ──
    existing = db.execute(text("SELECT COUNT(*) FROM student_answers WHERE student_id=:s AND exam_record_id='demo_exam_001'"), {"s": SID}).fetchone()[0]
    if existing >= 10:
        print(f"李雨萱数据已存在 ({existing} 条答题记录), 跳过。")
        db.close()
        return

    # ── 清理旧数据 ──
    for t,c,v in [
        ('student_answers', 'student_id', SID),
        ('parent_notifications', 'parent_id', PID),
        ('student_parent_bindings', 'parent_id', PID),
        ('exam_records', 'record_id', 'demo_exam_001'),
    ]: db.execute(text(f"DELETE FROM {t} WHERE {c}=:v"), {"v": v})
    db.execute(text("DELETE FROM questions WHERE record_id=:r"), {"r": "demo_exam_001"})
    db.execute(text("DELETE FROM accounts WHERE username IN (:a,:b)"), {"a": SID, "b": "lijg"})
    db.execute(text("DELETE FROM students WHERE student_id=:s"), {"s": SID})
    db.execute(text("DELETE FROM parents WHERE parent_id=:p"), {"p": PID})
    db.commit()

    # ── 1. Students ──
    db.execute(text("""INSERT INTO students (student_id,name,class_id,barrier_type,exercises_completed,last_exercise_at,status,bind_code)
        VALUES (:s,'李雨萱','class_2025_1',:bt,26,:la,'approved','582910')"""),
        {"s": SID, "bt": json.dumps({"concept":0.35,"reading":0.45,"expression":0.20}), "la": datetime.utcnow() - timedelta(hours=3)})

    # ── 2. Accounts ──
    db.execute(text("INSERT INTO accounts(account_id,role,username,password_hash,student_id,status) VALUES (:a,'student',:u,:p,:s,'active')"),
        {"a": "acct_lyx", "u": SID, "p": PW, "s": SID})
    db.execute(text("INSERT INTO accounts(account_id,role,username,password_hash,parent_id,status) VALUES (:a,'parent',:u,:p,:pp,'active')"),
        {"a": "acct_ljgo", "u": "lijg", "p": PW, "pp": PID})

    # ── 3. Parents + Binding ──
    db.execute(text("INSERT INTO parents(parent_id,name,phone,password_hash,status) VALUES (:p,'李建国','13812345678',:pw,'active')"), {"p": PID, "pw": PW})
    db.execute(text("INSERT INTO student_parent_bindings(binding_id,student_id,parent_id,relation,bind_code,status) VALUES ('bind_lyx',:s,:p,'父亲','582910','active')"), {"s": SID, "p": PID})

    # ── 4. Exam Record (published) ──
    db.execute(text("""INSERT INTO exam_records(record_id,class_id,name,type,total_students,present_students,exam_date,question_stats)
        VALUES (:r,'class_2025_1','高一(1)班 盐类水解&离子反应 单元练习','PRACTICE',1,1,:d,:s)"""),
        {"r": "demo_exam_001", "d": datetime.utcnow() - timedelta(days=1), "s": json.dumps({"published":True,"question_count":10,"knowledge_points":["盐类水解","离子反应","氧化还原","化学平衡","元素周期律","物质的量","有机化学","电化学"]})})

    # ── 5. Questions (10道, 链接到 demo_exam_001) ──
    for i, q in enumerate(QUESTIONS):
        db.execute(text("""INSERT INTO questions(question_id,record_id,content,options,answer,analysis,knowledge_points,difficulty,source,audit_status)
            VALUES (:q,:r,:c,:o,:a,:al,:k,:d,'manual','passed')"""), {
            "q": f"demo_q_{i:02d}", "r": "demo_exam_001",
            "c": q["content"], "o": json.dumps(q["options"]), "a": q["answer"], "al": q["analysis"],
            "k": json.dumps(q["knowledge_points"]), "d": q["difficulty"],
        })

    # ── 6. Student Answers (26条, 73%正确率) ──
    # 每道题被做了2-3次, 正确率随机但有规律: 简单题正确率高, 难题正确率低
    perf = {"easy": 0.85, "medium": 0.70, "hard": 0.50}
    total = correct = 0
    for day_offset in range(7, 0, -1):
        day = datetime.utcnow() - timedelta(days=day_offset)
        # 每天做3-4道题
        day_questions = random.sample(range(10), random.randint(3, 4))
        for qi in day_questions:
            q = QUESTIONS[qi]
            ok = random.random() < perf.get(q["difficulty"], 0.7)
            total += 1
            if ok: correct += 1
            aid = f"demo_a_{day_offset}_{qi}"
            db.execute(text("""INSERT INTO student_answers(answer_id,student_id,question_id,exam_record_id,student_answer,is_correct,answered_at)
                VALUES (:a,:s,:q,:r,:an,:ok,:at)"""), {
                "a": aid, "s": SID, "q": f"demo_q_{qi:02d}", "r": "demo_exam_001",
                "an": q["answer"] if ok else random.choice([o[0] for o in [opt.split(".")[0] for opt in q["options"]] if o[0] != q["answer"]]),
                "ok": ok, "at": day + timedelta(hours=random.randint(18, 22), minutes=random.randint(0, 59)),
            })

    # ── 7. Parent Notifications ──
    for nid, typ, title, content, ago in [
        ("dn1", "weekly_report", "📋 李雨萱本周学习报告", f"完成{total}道练习,正确率{int(correct/total*100)}%。薄弱点:盐类水解、离子反应。审题仔细度需加强。", 2),
        ("dn2", "daily_report", "今日练习完成—离子反应专题", "完成5道选择题,正确率80%。离子方程式书写进步明显!", 24),
    ]:
        db.execute(text("""INSERT INTO parent_notifications(notification_id,parent_id,student_id,type,title,content,is_read,sent_at)
            VALUES (:n,:p,:s,:t,:ti,:c,:r,:a)"""),
            {"n": nid, "p": PID, "s": SID, "t": typ, "ti": title, "c": content, "r": False, "a": datetime.utcnow() - timedelta(hours=ago)})

    db.commit()

    # ── Verify ──
    print(f"李雨萱: {SID} / 123456  bind=582910")
    print(f"家长: lijg / 123456")
    print(f"题目: {len(QUESTIONS)}道 (demo_q_00~demo_q_09)")
    print(f"答题: {total}条, 正确{correct}道 ({int(correct/total*100)}%)")
    print(f"通知: 2条")

    # Check all tables
    print(f"  学生: {db.execute(text('SELECT COUNT(*) FROM students WHERE student_id=:s'),{'s':SID}).fetchone()[0]} 条")
    print(f"  考试: {db.execute(text('SELECT COUNT(*) FROM exam_records WHERE record_id=:r'),{'r':'demo_exam_001'}).fetchone()[0]} 条")
    print(f"  题目: {db.execute(text('SELECT COUNT(*) FROM questions WHERE record_id=:r'),{'r':'demo_exam_001'}).fetchone()[0]} 条")
    print(f"  答题: {db.execute(text('SELECT COUNT(*) FROM student_answers WHERE student_id=:s'),{'s':SID}).fetchone()[0]} 条")
    print(f"  通知: {db.execute(text('SELECT COUNT(*) FROM parent_notifications WHERE parent_id=:p'),{'p':PID}).fetchone()[0]} 条")
    db.close()
    print("\n✓ 数据初始化完成。重启不会丢失。")

if __name__ == '__main__':
    main()
