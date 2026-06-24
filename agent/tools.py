"""ChemAI Skills — pydantic-ai tool_plain 版本
每个 skill 是一个 async 函数，带 type hints。注册到 pydantic-ai Agent 时自动生成 JSON schema。
"""
import json
from dotenv import load_dotenv

load_dotenv()

# ── 1. search_exam_bank ──

async def search_exam_bank(
    keyword: str = "",
    year: int = 0,
    difficulty: str = "",
    limit: int = 5,
) -> str:
    """考试工作台 — 搜索历年高考化学真题

    何时用：用户明确说"搜索真题""看看有什么题"时使用。如果用户说的是"出题""出卷""组卷"，应该直接调 show_exam_workbench，不要先搜真题
    会发生什么：返回真题列表（含年份、来源、答案），在对话中展示
    下一步：简洁展示搜索结果即可，不要追问过多后续选项。用户会主动告诉你下一步需求"""
    from app.services.exam_bank import exam_bank_service

    results = exam_bank_service.search_questions(
        knowledge_point=keyword or None,
        year=year if year else None,
        difficulty=difficulty or None,
        limit=limit,
    )
    if not results:
        return json.dumps({
            "total": 0,
            "questions": [],
            "hint": "题库中暂无匹配结果。请向用户确认更具体的搜索条件（知识点、年份），而不是反复尝试不同关键词。",
            "_route": {"navigate": False},
        }, ensure_ascii=False)

    return json.dumps({
        "total": len(results),
        "questions": [
            {
                "source": q.source,
                "year": q.year,
                "content": q.content[:200],
                "answer": q.answer,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty,
            }
            for q in results
        ],
        "_route": {"navigate": False},
    }, ensure_ascii=False)


# ── 2. web_search ──

async def web_search(query: str = "") -> str:
    """联网搜索 — 查询最新化学信息、高考动态、教学资源

    何时用：用户询问的信息超出训练数据范围（如"2025高考大纲"）、需要最新政策或新闻
    会发生什么：返回联网搜索结果摘要，在对话中展示
    下一步：基于搜索结果回答用户问题；如需出题 → generate_questions"""
    import os, httpx

    api_key = os.getenv("XIAOMI_API_KEY", "")
    if not api_key:
        return json.dumps({"error": "未配置 MiMo API Key"})

    payload = {
        "model": "mimo-v2.5",
        "messages": [{"role": "user", "content": query}],
        "enable_search": True,
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.xiaomimimo.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({
                "query": query,
                "result": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {}),
            }, ensure_ascii=False)
        return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:200]})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── 3. generate_questions ──

async def generate_questions(
    knowledge_points: str = "",
    difficulty: str = "medium",
    quantity: int = 5,
    student_name: str = "",
) -> str:
    """[DEPRECATED for agent use] 考试工作台 — 生成高中化学选择题

    Agent 不应再调用此工具。请使用 navigate_to_exam_workbench 代替——
    通过对话收集参数后跳转考试工作台，由页面端完成题目生成。
    此函数保留供考试工作台页面直接调用。"""
    import re
    from agent.provider.deepseek import DeepSeekProvider
    from app.services.chemical_balance import audit_chemical_equation

    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]

    provider = DeepSeekProvider()

    system_prompt = """你是资深高中化学教师。根据知识点生成高质量的化学选择题。

要求:
1. 题目科学性100%正确，化学方程式必须配平
2. 4个选项，有区分度
3. 注明正确答案和解析
4. 适当设置陷阱选项

返回纯JSON（不要markdown代码块）:
{
  "questions": [
    {
      "content": "题目正文",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "A",
      "explanation": "解析",
      "knowledge_points": ["知识点1"],
      "difficulty": "medium",
      "has_equation": false
    }
  ]
}"""

    prompt = f"请生成{quantity}道{difficulty}难度的高中化学题。知识点: {', '.join(kps) if kps else '高中化学综合'}"

    try:
        result = await provider.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=4096,
        )

        content = result.content
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = {"questions": []}

        questions = data.get("questions", [])
        audit_results = []
        for q in questions:
            if q.get("has_equation") or any(
                kw in q.get("content", "") for kw in ["→", "=", "->", "方程式", "反应"]
            ):
                eq_match = re.search(r"([\d\w\(\)\+\s→=->]+)", q.get("content", ""))
                if eq_match:
                    audit = audit_chemical_equation(eq_match.group(1))
                    audit_results.append({
                        "question_idx": questions.index(q),
                        "equation": eq_match.group(1),
                        "audit": audit["overall_status"],
                    })

        await provider.close()
        return json.dumps({
            "questions": questions,
            "total": len(questions),
            "audit_results": audit_results,
            "_route": {
                "navigate": not bool(student_name),
                "page": "exam-v2" if not student_name else None,
                "actions": [{"action": "openTab", "payload": "generate"}] if not student_name else [],
                "populate": {"target": "questions", "data": {"questions": questions, "total": len(questions)}} if not student_name else None,
            },
        }, ensure_ascii=False)

    except Exception as e:
        await provider.close()
        return json.dumps({"error": f"出题失败: {str(e)}", "questions": []}, ensure_ascii=False)


# ── 4. diagnose_barrier ──

async def diagnose_barrier(
    student_id: str = "",
    student_name: str = "",
    class_id: str = "",
) -> str:
    """学情诊断 — 诊断学生的化学学习障碍类型（概念理解/审题障碍/表述障碍）

    何时用：用户询问某个学生或班级的学习情况、错题原因、薄弱环节
    会发生什么：个体诊断返回学生障碍分布和主导障碍类型；班级诊断返回全班障碍分布统计
    下一步：个体诊断 → 根据障碍类型推荐针对性练习（assign_adaptive_practice）；班级诊断 → 跳转诊断页面展示图表"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    # If student_id looks like a name (non-digits), auto-resolve to real ID
    if student_id and not student_id.isdigit():
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_id}%"},
        ).fetchall()
        if not rows:
            session.close()
            return json.dumps({"error": f"未找到名为 '{student_id}' 的学生", "hint": "请确认姓名是否正确，或提供学号查询", "_route": {"navigate": False}})
        if len(rows) > 1:
            session.close()
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({"multiple_matches": candidates, "hint": "找到多个匹配学生，请提供完整学号", "_route": {"navigate": False}})
        student_id = rows[0][0]

    # Allow lookup by student name param
    if student_name and not student_id:
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_name}%"},
        ).fetchall()
        if not rows:
            session.close()
            return json.dumps({"error": f"未找到名为 '{student_name}' 的学生", "hint": "请确认姓名是否正确，或提供学号/班级ID查询", "_route": {"navigate": False}})
        if len(rows) > 1:
            session.close()
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({"multiple_matches": candidates, "hint": "找到多个匹配学生，请指定学号", "_route": {"navigate": False}})
        student_id = rows[0][0]

    if student_id:
        row = session.execute(
            text("SELECT name, barrier_type, exercises_completed FROM students WHERE student_id = :sid"),
            {"sid": student_id},
        ).fetchone()
        session.close()

        if not row:
            return json.dumps({"error": f"学生 {student_id} 不存在", "_route": {"navigate": False}})

        barrier = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        dominant = max(barrier.items(), key=lambda x: x[1]) if barrier else ("unknown", 0)

        return json.dumps({
            "student_id": student_id,
            "student_name": row[0],
            "barrier_distribution": barrier,
            "dominant_barrier": dominant[0],
            "exercises_completed": row[2] or 0,
            "_route": {"navigate": False},
        }, ensure_ascii=False)

    elif class_id:
        rows = session.execute(
            text("SELECT student_id, name, barrier_type FROM students WHERE class_id = :cid"),
            {"cid": class_id},
        ).fetchall()
        session.close()

        students = []
        concept_count = reading_count = expression_count = 0
        for row in rows:
            barrier = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            if barrier:
                students.append({
                    "student_id": row[0],
                    "student_name": row[1],
                    "dominant": max(barrier.items(), key=lambda x: x[1])[0],
                })
                for bt, val in barrier.items():
                    if val >= 0.5:
                        if bt == "concept": concept_count += 1
                        elif bt == "reading": reading_count += 1
                        elif bt == "expression": expression_count += 1

        _data = {
            "class_id": class_id,
            "total_students": len(students),
            "barrier_distribution": {"concept": concept_count, "reading": reading_count, "expression": expression_count},
            "students": students[:10],
        }
        return json.dumps({
            **_data,
            "_component": {
                "component": "diagnosis",
                "params": _data,
            },
        }, ensure_ascii=False)

    session.close()
    return json.dumps({"error": "请提供 student_id 或 class_id", "_route": {"navigate": False}})


# ── 5. chemistry_tutor ──

async def chemistry_tutor(
    question: str = "",
    student_level: str = "中等",
) -> str:
    """聊天辅导 — 引导式解答化学问题

    何时用：学生提问化学概念、解题思路、知识点讲解等非出题类问题
    会发生什么：以引导式教学分步讲解，不直接给答案；根据学生水平调整讲解深度
    下一步：如学生仍有疑问 → 继续解答；如需要出题练习 → generate_questions"""
    from agent.provider.deepseek import DeepSeekProvider

    provider = DeepSeekProvider()

    system_prompt = f"""你是高中化学AI助教。学生水平: {student_level}。

教学原则:
1. 引导式教学: 不直接给答案，先问学生"你是怎么想的"
2. 分步讲解: 复杂问题拆成2-3步，每步确认理解
3. 联系考点: 提及高考中的常见题型
4. 鼓励为主: 对正确思路给予肯定
5. 单次回复不超过500字
6. 不确定时诚实说不知道"""

    result = await provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.7,
        max_tokens=1024,
    )

    await provider.close()
    return json.dumps({"answer": result.content, "model": result.model}, ensure_ascii=False)


# ── 6. simulate_experiment ──

async def simulate_experiment(experiment_name: str = "") -> str:
    """实验模拟 — 模拟高中化学实验过程

    何时用：用户想了解某个实验的操作步骤、现象、原理，或说"模拟XX实验"
    会发生什么：生成实验步骤、预测现象、写出方程式、解释原理，附带安全提醒
    下一步：基于实验结果回答用户追问；如需配平实验方程式 → balance_equation"""
    import re
    from agent.provider.deepseek import DeepSeekProvider

    provider = DeepSeekProvider()

    system_prompt = """你是高中化学实验教学专家。为指定实验生成完整报告。

返回JSON:
{
  "experiment_name": "实验名称",
  "objectives": ["实验目的1", "实验目的2"],
  "equipment": ["仪器1", "药品1"],
  "steps": ["步骤1: ...", "步骤2: ..."],
  "expected_phenomena": ["现象1: ...", "现象2: ..."],
  "equations": ["化学方程式1", "化学方程式2"],
  "principles": ["原理1", "原理2"],
  "safety": ["安全提醒1", "安全提醒2"],
  "exam_tips": ["高考考点提示"]
}"""

    result = await provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请生成实验报告: {experiment_name}"},
        ],
        temperature=0.5,
        max_tokens=2048,
    )

    content = result.content
    json_match = re.search(r"\{[\s\S]*\}", content)

    await provider.close()

    if json_match:
        return json_match.group()
    return json.dumps({"experiment_name": experiment_name, "error": "JSON解析失败"}, ensure_ascii=False)


# ── 7. balance_equation ──

async def balance_equation(equation: str = "") -> str:
    """方程式配平 — 审核化学方程式的配平正确性

    何时用：用户发来一个化学方程式要求检查配平，或出题后需要审核题目中的方程式
    会发生什么：检查等式两侧各元素的原子数量，返回配平状态和各元素计数
    下一步：如配平正确 → 告知用户；如有问题 → 指出不平衡的元素和修正建议"""
    from app.services.chemical_balance import audit_chemical_equation

    result = audit_chemical_equation(equation)
    return json.dumps(result, ensure_ascii=False)


# ── 8. weekly_report ──

async def weekly_report(student_id: str = "", student_name: str = "", class_name: str = "") -> str:
    """学习报告 — 生成学生或班级的化学学习周报

    何时用：用户（通常为家长或老师）要求查看学习报告、本周学习情况
    会发生什么：个人报告包含学习内容、掌握情况、成长空间和家庭配合建议；班级报告包含整体统计
    下一步：个人报告 → 对话中展示；班级报告 → 可跳转诊断页面查看图表"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from agent.provider.deepseek import DeepSeekProvider
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    # If student_id looks like a name (non-digits), auto-resolve to real ID
    if student_id and not student_id.isdigit():
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_id}%"},
        ).fetchall()
        if not rows:
            session.close()
            return json.dumps({"error": f"未找到名为 '{student_id}' 的学生", "_route": {"navigate": False}})
        if len(rows) > 1:
            session.close()
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({"multiple_matches": candidates, "hint": "找到多个匹配学生，请提供完整学号", "_route": {"navigate": False}})
        student_id = rows[0][0]

    # Allow lookup by student name param
    if student_name and not student_id:
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_name}%"},
        ).fetchall()
        if not rows:
            session.close()
            return json.dumps({"error": f"未找到名为 '{student_name}' 的学生", "_route": {"navigate": False}})
        if len(rows) > 1:
            session.close()
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({"multiple_matches": candidates, "hint": "找到多个匹配学生，请指定学号", "_route": {"navigate": False}})
        student_id = rows[0][0]

    student_row = session.execute(
        text("SELECT name, class_id, barrier_type, exercises_completed FROM students WHERE student_id = :sid"),
        {"sid": student_id},
    ).fetchone()

    if not student_row:
        session.close()
        return json.dumps({"error": f"学生 {student_id} 不存在", "_route": {"navigate": False}})

    student_name_resolved = student_row[0]
    barrier = json.loads(student_row[2]) if isinstance(student_row[2], str) else student_row[2]

    exam_count = session.execute(
        text("SELECT COUNT(*) FROM exam_records WHERE class_id = :cid"),
        {"cid": student_row[1]},
    ).fetchone()[0]

    session.close()

    provider = DeepSeekProvider()

    system_prompt = """你是ChemAI家长助手。生成学生本周学习报告。

原则:
- 鼓励为主，先肯定进步
- 用通俗语言，不用教育学术语
- 给出家长可操作的建议
- 不制造焦虑"""

    prompt = f"""请为 {student_name_resolved} 生成本周化学学习报告:

学习数据:
- 本周参加了 {exam_count} 次课堂练习
- 学习特点: {json.dumps(barrier, ensure_ascii=False)}

请生成200字以内的报告，直接回复文本，不要JSON."""

    result = await provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=512,
    )

    await provider.close()

    return json.dumps({
        "student_name": student_name_resolved,
        "report": result.content,
        "exam_count": exam_count,
    }, ensure_ascii=False)


# ── 9. import_exam_paper ──

async def import_exam_paper(
    pdf_path: str = "",
    source: str = "未知来源",
    year: int = 2025,
    auto_approve: bool = False,
) -> str:
    """试卷导入 — 上传PDF试卷自动提取化学题目并入库

    何时用：用户有PDF格式的试卷需要导入题库，或说"导入这份试卷"
    会发生什么：调用MinerU OCR解析PDF，提取化学题目，审核方程式配平，自动入库
    下一步：导入完成 → 告知用户导入数量和题库位置；需调 request_approval 确认"""
    import os, re

    if not pdf_path or not os.path.exists(pdf_path):
        return json.dumps({"error": f"PDF文件不存在: {pdf_path}"})

    # 1. 尝试调 MinerU
    mineru_available = False
    try:
        from app.services.mineru_service import MinerUClient
        client = MinerUClient()
        raw_questions = await client.extract_questions(pdf_path)
        mineru_available = True
    except (ImportError, Exception):
        raw_questions = [{
            "number": "N/A",
            "content": f"PDF解析需要 MinerU 服务。请安装 Docker 并启动 MinerU 容器。文件: {pdf_path}",
            "options": [],
            "answer": "",
        }]

    # 2. 化学审核
    from app.services.chemical_balance import audit_chemical_equation

    reviewed = []
    passed = 0
    for q in raw_questions:
        audit = None
        content = q.get("content", "") + q.get("question", "")
        if any(kw in content for kw in ["→", "=", "反应", "方程式"]):
            eq_match = re.search(r"([\d\w\(\)\+\s→=->]+)", content)
            if eq_match:
                audit = audit_chemical_equation(eq_match.group(1))

        reviewed.append({
            **q,
            "audit_status": audit["overall_status"] if audit else "no_equation",
            "audit_detail": audit if audit else None,
        })
        if audit is None or audit["overall_status"] == "passed":
            passed += 1

    # 3. 入库
    saved = 0
    if auto_approve:
        try:
            from app.services.exam_bank import exam_bank_service
            saved = exam_bank_service.batch_import(reviewed, source, year)
        except Exception as e:
            return json.dumps({
                "extracted": len(raw_questions),
                "passed_audit": passed,
                "saved": 0,
                "error": f"入库失败: {str(e)}",
                "mineru_used": mineru_available,
            }, ensure_ascii=False)

    return json.dumps({
        "extracted": len(raw_questions),
        "passed_audit": passed,
        "saved": saved,
        "auto_approved": auto_approve,
        "needs_review": len(reviewed) - passed,
        "questions": reviewed if not auto_approve else None,
        "mineru_used": mineru_available,
    }, ensure_ascii=False)


# ── 10. assign_adaptive_practice ──

async def assign_adaptive_practice(
    class_id: str = "",
    knowledge_points: str = "",
    question_count: int = 5,
) -> str:
    """自适应练习 — 根据学生障碍类型布置个性化练习

    何时用：诊断完成后，老师要求给班级/学生布置针对性练习
    会发生什么：为每个学生生成符合其最近发展区的个性化化学题，自动分配
    下一步：分配完成 → 告知老师分配结果；此工具需要先调 request_approval 确认"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    try:
        from app.api.practice import _calculate_zpd_difficulty, _get_weak_kps, _get_dominant_barrier
    except ImportError:
        def _calculate_zpd_difficulty(s): return "medium"
        def _get_weak_kps(s): return []
        def _get_dominant_barrier(s): return "concept"

    from app.services.llm_service import llm_service
    from app.models.database import Student, get_db

    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]

    db = next(get_db())
    try:
        students = db.query(Student).filter(Student.class_id == class_id).all()
        if not students:
            return json.dumps({"error": f"班级 {class_id} 无学生", "_route": {"navigate": False}})

        assigned = []
        for student in students[:5]:
            zpd = _calculate_zpd_difficulty(student.student_id, db)
            barrier = _get_dominant_barrier(student.student_id, db)
            weak = _get_weak_kps(student.student_id, db)
            use_kps = weak if weak else kps

            result = llm_service.generate_questions(
                knowledge_points=use_kps, difficulty=zpd,
                quantity=question_count, question_types=["choice"],
            )
            if result.get("success"):
                assigned.append({
                    "student_name": student.name,
                    "zpd_difficulty": zpd,
                    "barrier": barrier,
                    "question_count": question_count,
                    "weak_kps": weak,
                })

        return json.dumps({"assigned_count": len(assigned), "assigned": assigned, "_route": {"navigate": False}}, ensure_ascii=False)
    finally:
        db.close()


# ── 11. save_to_bank ──

async def save_to_bank(
    questions: str = "",
    knowledge_points: str = "",
    set_name: str = "",
    description: str = "",
) -> str:
    """考试工作台 — 将生成的题目保存到题库

    何时用：generate_questions 出完题且没有指定学生姓名时，必须调此工具保存
    会发生什么：创建题库文件夹（自动命名），将题目存入数据库，可在考试工作台中管理和复用
    下一步：保存后告知用户文件夹名，引导用户去考试工作台查看 → 页面跳转到 exam-v2 题库 tab"""
    import sys, os
    from datetime import datetime
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.models.database import get_db, QuestionSet, QuestionSetItem, Question
    from app.models.database import QuestionSource, AuditStatus, Difficulty

    # Parse questions
    try:
        if isinstance(questions, str):
            data = json.loads(questions)
        else:
            data = questions
        q_list = data.get("questions", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "题目数据格式无效", "_route": {"navigate": False}}, ensure_ascii=False)

    if not q_list:
        return json.dumps({"error": "没有可保存的题目", "_route": {"navigate": False}}, ensure_ascii=False)

    # Auto-generate set name
    if not set_name:
        kps = knowledge_points or "综合"
        ts = datetime.now().strftime("%m%d%H%M")
        set_name = f"AI生成-{kps}-{ts}"

    db = next(get_db())
    try:
        set_id = f"qset_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        question_set = QuestionSet(
            set_id=set_id,
            name=set_name,
            teacher_id=None,
            region="AI生成",
            year=None,
            source="agent",
            description=description or f"Agent 自动生成: {knowledge_points}",
            question_count=0,
            is_system=False,
        )
        db.add(question_set)

        import_count = 0
        for i, q in enumerate(q_list):
            question_id = f"q_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"
            difficulty = Difficulty.MEDIUM
            if q.get("difficulty") == "easy":
                difficulty = Difficulty.EASY
            elif q.get("difficulty") == "hard":
                difficulty = Difficulty.HARD

            new_q = Question(
                question_id=question_id,
                record_id=None,
                content=q.get("content", ""),
                options=q.get("options"),
                answer=str(q.get("answer", "")),
                analysis=q.get("explanation") or q.get("analysis", ""),
                knowledge_points=q.get("knowledge_points", []),
                difficulty=difficulty,
                source=QuestionSource.MANUAL_SELECTED,
                source_exam=set_name,
                audit_status=AuditStatus.PASSED,
            )
            db.add(new_q)

            item = QuestionSetItem(
                item_id=f"qsi_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}",
                set_id=set_id,
                question_id=question_id,
                sort_order=i + 1,
            )
            db.add(item)
            import_count += 1

        question_set.question_count = import_count
        db.commit()

        return json.dumps({
            "saved": True,
            "set_id": set_id,
            "set_name": set_name,
            "count": import_count,
            "message": f"已保存 {import_count} 道题目到题库「{set_name}」",
            "_route": {
                "navigate": True,
                "page": "exam-v2",
                "populate": {"target": "exam-set", "data": {"set_id": set_id, "set_name": set_name}},
                "actions": [{"action": "openTab", "payload": "bank"}],
            },
        }, ensure_ascii=False)

    except Exception as e:
        db.rollback()
        return json.dumps({"error": f"保存失败: {str(e)}", "_route": {"navigate": False}}, ensure_ascii=False)
    finally:
        db.close()


# ── 12. show_exam_workbench ──

async def show_exam_workbench(
    knowledge_points: str = "",
    difficulty: str = "medium",
    question_types: str = "",
    variant_source: str = "",
    set_name: str = "",
) -> str:
    """考试工作台 — 在聊天中打开内联出题面板

    何时用：用户说"出题""出卷""生成题目""组卷"等任何出题意图时，立即调用！
    不要再反问用户、不要先搜真题、不要确认参数——直接展示面板让用户在面板里配置。
    会发生什么：在聊天界面中渲染考试工作台面板，用户可直接在面板中配置参数、出题、预览、编辑、保存
    下一步：用户在面板中操作完成后，Agent 收到总结消息。question_types 格式如 "single_choice:5,fill_blank:2"
    """
    import logging
    _log = logging.getLogger(__name__)

    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]

    types = []
    if question_types:
        for item in question_types.split(","):
            parts = item.strip().split(":")
            if len(parts) == 2:
                val, qty = parts[0].strip(), int(parts[1].strip())
                types.append({"val": val, "active": True, "qty": qty})

    if not types:
        types = [{"val": "single_choice", "active": True, "qty": 3}]

    _data = {
        "knowledge_points": kps,
        "difficulty": difficulty,
        "types": types,
    }
    if variant_source:
        _data["variant_source"] = variant_source
    if set_name:
        _data["set_name"] = set_name

    _log.info(f"[show_exam_workbench] kps={kps}, diff={difficulty}, types={types}")

    return json.dumps({
        "message": f"参数已确认：{knowledge_points}，{difficulty}难度。请在下方面板中生成题目。",
        "_component": {
            "component": "exam-workbench",
            "params": _data,
        },
    }, ensure_ascii=False)


# ── 13. show_diagnosis ──

async def show_diagnosis(student_id: str = "", student_name: str = "", class_id: str = "") -> str:
    """学情诊断 — 在聊天中展示诊断结果和图表

    何时用：用户要求查看学生或班级的诊断结果
    会发生什么：在聊天中渲染诊断面板，包含障碍分布图和关键指标
    下一步：用户可点击"针对出题"快捷按钮，跳转到出题面板
    """
    import logging
    _log = logging.getLogger(__name__)

    # Call diagnose_barrier to get data
    from agent.tools import diagnose_barrier as _diag
    diag_result = await _diag(student_id=student_id, student_name=student_name, class_id=class_id)

    try:
        data = json.loads(diag_result) if isinstance(diag_result, str) else diag_result
    except (json.JSONDecodeError, TypeError):
        data = {"error": "诊断数据解析失败"}

    if "error" in data:
        return json.dumps({"message": data.get("error", "诊断失败"), "_component": None}, ensure_ascii=False)

    return json.dumps({
        "message": "诊断结果已生成，请查看下方图表。",
        "_component": {
            "component": "diagnosis",
            "params": data,
        },
    }, ensure_ascii=False)


# ── 15. list_banks ──

async def list_banks() -> str:
    """题库管理 — 列出所有题库文件夹

    何时用：用户想查看有哪些题库文件夹，或需要知道题库名称和题目数量
    会发生什么：返回题库列表（set_id、名称、题目数量）
    下一步：用户可能要求删除某个题库（delete_bank）或查看某个题库的内容
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.models.database import get_db, QuestionSet

    db = next(get_db())
    try:
        sets = db.query(QuestionSet).order_by(QuestionSet.created_at.desc()).all()
        result = [{
            "set_id": s.set_id,
            "name": s.name,
            "question_count": s.question_count or 0,
            "created_at": str(s.created_at) if s.created_at else "",
        } for s in sets]
        return json.dumps({"banks": result, "total": len(result)}, ensure_ascii=False)
    finally:
        db.close()


# ── 16. delete_bank ──

async def delete_bank(set_id: str = "") -> str:
    """题库管理 — 删除题库文件夹及其中所有题目

    何时用：用户明确要求删除某个题库文件夹
    会发生什么：删除题库文件夹和其中的题目关联（题目本身保留）
    下一步：告知用户删除结果

    注意：此操作不可逆，需要先调 request_approval 确认
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.models.database import get_db, QuestionSet, QuestionSetItem

    if not set_id:
        return json.dumps({"error": "请指定要删除的题库 set_id"}, ensure_ascii=False)

    db = next(get_db())
    try:
        qs = db.query(QuestionSet).filter(QuestionSet.set_id == set_id).first()
        if not qs:
            return json.dumps({"error": f"题库 {set_id} 不存在"}, ensure_ascii=False)

        name = qs.name
        count = qs.question_count or 0

        # Delete QuestionSetItems first, then QuestionSet
        db.query(QuestionSetItem).filter(QuestionSetItem.set_id == set_id).delete()
        db.delete(qs)
        db.commit()

        return json.dumps({
            "deleted": True,
            "set_id": set_id,
            "name": name,
            "question_count": count,
            "message": f"已删除题库「{name}」（含 {count} 道题目关联）",
        }, ensure_ascii=False)
    except Exception as e:
        db.rollback()
        return json.dumps({"error": f"删除失败: {str(e)}"}, ensure_ascii=False)
    finally:
        db.close()


# ── 16. show_students ──

async def show_students(
    class_id: str = "",
    class_name: str = "",
    filter_barrier: str = "",
) -> str:
    """学生/班级列表 — 展示班级学生或全部班级

    何时用：用户问"有几个班""有哪些学生""找问题大的学生""班里谁最薄弱"
    会发生什么：未指定班级时列出所有班级；指定班级时渲染学生列表面板
    下一步：用户点击学生卡片 → 触发该学生的诊断
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    # Resolve class_name → class_id (with flexible matching)
    if class_name and not class_id:
        cn = str.maketrans("一二三四五六七八九十", "1234567890")
        import re as _re

        # Step 1: exact match
        row = session.execute(
            text("SELECT class_id, name FROM classes WHERE name = :n"),
            {"n": class_name},
        ).fetchone()

        # Step 2: LIKE match
        if not row:
            row = session.execute(
                text("SELECT class_id, name FROM classes WHERE name LIKE :n"),
                {"n": f"%{class_name}%"},
            ).fetchone()

        # Step 3: normalize class number (高一一班/高一(1)班/高一（一）班 → match 高一(1)班)
        if not row:
            clean = class_name.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
            m = _re.match(r"(.+)([一二三四五六七八九十\d]+)\s*班", clean)
            if m:
                prefix = m.group(1)
                num = m.group(2).translate(cn)
                pattern = f"%{prefix}%{num}%班%"
                row = session.execute(
                    text("SELECT class_id, name FROM classes WHERE REPLACE(REPLACE(name, '(', ''), ')', '') LIKE :p"),
                    {"p": pattern},
                ).fetchone()

        if not row:
            session.close()
            return json.dumps({"message": f"未找到班级 '{class_name}'，可用班级：高一(1)班、高一(2)班", "_component": None}, ensure_ascii=False)
        class_id = row[0]

    if not class_id:
        # No class specified → list all classes
        rows = session.execute(
            text("SELECT class_id, name, grade, student_count FROM classes ORDER BY name")
        ).fetchall()
        session.close()
        if not rows:
            return json.dumps({"result": "暂无班级数据"}, ensure_ascii=False)
        classes = [{"class_id": r[0], "name": r[1], "grade": r[2], "student_count": r[3] or 0} for r in rows]
        summary = "共" + str(len(classes)) + "个班级：" + "、".join(c["name"] + "(" + str(c["student_count"]) + "人)" for c in classes)
        return json.dumps({"result": summary, "classes": classes, "total": len(classes)}, ensure_ascii=False)

    # Get class name
    cls_row = session.execute(
        text("SELECT name FROM classes WHERE class_id = :cid"), {"cid": class_id}
    ).fetchone()
    resolved_class_name = cls_row[0] if cls_row else class_id

    # Query students with barrier data
    rows = session.execute(
        text("SELECT student_id, name, barrier_type, exercises_completed FROM students WHERE class_id = :cid ORDER BY exercises_completed ASC"),
        {"cid": class_id},
    ).fetchall()
    session.close()

    if not rows:
        return json.dumps({"message": f"{resolved_class_name} 暂无学生", "_component": None}, ensure_ascii=False)

    students = []
    for r in rows:
        barrier = json.loads(r[2]) if isinstance(r[2], str) else (r[2] or {})
        if barrier:
            dominant = max(barrier.items(), key=lambda x: x[1])
            barrier_type = dominant[0]
            barrier_score = dominant[1]
        else:
            barrier_type = "unknown"
            barrier_score = 0

        # Filter by barrier type if specified
        if filter_barrier:
            bt_map = {"计算": "concept", "概念": "concept", "审题": "reading", "阅读": "reading", "表述": "expression", "表达": "expression"}
            target = bt_map.get(filter_barrier, filter_barrier)
            if barrier_type != target:
                continue

        students.append({
            "student_id": r[0],
            "name": r[1],
            "dominant_barrier": barrier_type,
            "barrier_score": round(barrier_score, 2),
            "exercises_completed": r[3] or 0,
        })

    if filter_barrier and not students:
        return json.dumps({"message": f"{resolved_class_name} 没有 {filter_barrier} 障碍的学生", "_component": None}, ensure_ascii=False)

    # Sort by barrier_score desc (worst first)
    students.sort(key=lambda s: s["barrier_score"], reverse=True)

    # Build summary for LLM (so it knows the tool succeeded)
    barrier_labels = {"concept": "计算能力", "reading": "审题障碍", "expression": "表述障碍", "unknown": "未诊断"}
    top5 = students[:5]
    top_summary = "、".join(
        f"{s['name']}({barrier_labels.get(s['dominant_barrier'], s['dominant_barrier'])} {int(s['barrier_score']*100)}%)"
        for s in top5
    )

    return json.dumps({
        "result": f"已找到{resolved_class_name} {len(students)}名学生，已在面板中展示。障碍最严重的前5名：{top_summary}。用户可在面板中搜索、点击学生卡片进行诊断。",
        "student_count": len(students),
        "top_barriers": [
            {"name": s["name"], "barrier": barrier_labels.get(s["dominant_barrier"], s["dominant_barrier"]), "score": s["barrier_score"]}
            for s in top5
        ],
        "_component": {
            "component": "student-list",
            "params": {
                "class_name": resolved_class_name,
                "class_id": class_id,
                "students": students,
            },
        },
    }, ensure_ascii=False)


# ── Tool list for factory ──

TOOLS = [
    search_exam_bank,
    web_search,
    show_exam_workbench,
    show_diagnosis,
    show_students,
    diagnose_barrier,
    chemistry_tutor,
    simulate_experiment,
    balance_equation,
    weekly_report,
    import_exam_paper,
    assign_adaptive_practice,
    save_to_bank,
    list_banks,
    delete_bank,
]
