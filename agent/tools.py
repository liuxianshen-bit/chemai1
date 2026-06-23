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

    何时用：用户明确说"搜索真题"或"看看有什么题"。出题时用户未给全参数时不要单独搜——先反问参数，参数齐了直接用 navigate_to_exam_workbench
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
            "_route": {
                "navigate": True,
                "page": "diagnosis",
                "actions": [
                    {"action": "selectClass", "payload": class_id},
                    {"action": "showPlan", "payload": ""},
                ],
                "populate": {"target": "diagnosis", "data": _data},
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

    _is_class = bool(class_name) and not bool(student_id) and not bool(student_name)
    return json.dumps({
        "student_name": student_name_resolved,
        "report": result.content,
        "exam_count": exam_count,
        "_route": {
            "navigate": _is_class,
            "page": "students" if _is_class else None,
            "actions": [{"action": "searchStudent", "payload": class_name}, {"action": "openWeeklyReport", "payload": ""}] if _is_class else [],
            "populate": {"target": "weeklyReport", "data": {"student_name": student_name_resolved, "report": result.content}} if _is_class else None,
        },
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


# ── 12. navigate_to_exam_workbench ──

async def navigate_to_exam_workbench(
    knowledge_points: str = "",
    difficulty: str = "medium",
    question_types: str = "",
    variant_source: str = "",
    set_name: str = "",
) -> str:
    """考试工作台 — 跳转到考试工作台并预填出题参数

    何时用：用户要求出题且已提供知识点+难度+题型参数时，优先调用此工具。
    不要再调 search_exam_bank 搜索——参数够了就直接跳转，不用先搜真题。
    会发生什么：跳转到考试工作台的 AI 出题 tab，自动预填所有字段并立即开始生成题目
    下一步：用户在考试工作台页面上预览题目、编辑、保存到题库。Agent 无需再做任何操作

    question_types 格式: "题型:数量,题型:数量"，如 "single_choice:5,fill_blank:2"
    可选题型: single_choice, fill_blank, calculation, experiment, inference
    """
    import logging
    _log = logging.getLogger(__name__)

    # Parse knowledge points
    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]

    # Parse question types
    types = []
    if question_types:
        for item in question_types.split(","):
            parts = item.strip().split(":")
            if len(parts) == 2:
                val, qty = parts[0].strip(), int(parts[1].strip())
                types.append({"val": val, "active": True, "qty": qty})

    if not types:
        types = [{"val": "single_choice", "active": True, "qty": 3}]

    # Assemble populate data for exam-v2 bridge
    _data = {
        "knowledge_points": kps,
        "difficulty": difficulty,
        "types": types,
    }
    if variant_source:
        _data["variant_source"] = variant_source
    if set_name:
        _data["set_name"] = set_name

    _log.info(f"[navigate_to_exam_workbench] kps={kps}, diff={difficulty}, types={types}")

    return json.dumps({
        "message": f"已为您准备好出题参数：{knowledge_points}，{difficulty}难度。正在跳转到考试工作台...",
        "_route": {
            "navigate": True,
            "page": "exam-v2",
            "params": {"knowledge_points": knowledge_points, "difficulty": difficulty},
            "actions": [
                {"action": "openTab", "payload": "generate"},
                {"action": "setTypes", "payload": question_types or "single_choice:3"},
            ],
            "populate": {"target": "exam-config", "data": _data},
        },
    }, ensure_ascii=False)


# ── Tool list for factory ──

TOOLS = [
    search_exam_bank,
    web_search,
    navigate_to_exam_workbench,
    diagnose_barrier,
    chemistry_tutor,
    simulate_experiment,
    balance_equation,
    weekly_report,
    import_exam_paper,
    assign_adaptive_practice,
    save_to_bank,
]
