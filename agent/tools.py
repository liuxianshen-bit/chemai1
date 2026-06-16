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
    """搜索历年高考化学真题。按知识点关键词、年份、难度筛选。"""
    from app.services.exam_bank import exam_bank_service

    results = exam_bank_service.search_questions(
        knowledge_point=keyword or None,
        year=year if year else None,
        difficulty=difficulty or None,
        limit=limit,
    )
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
    }, ensure_ascii=False)


# ── 2. web_search ──

async def web_search(query: str = "") -> str:
    """使用 MiMo 联网搜索功能查询实时化学信息、高考动态、教学资源。"""
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
) -> str:
    """根据知识点和难度生成高中化学选择题。内部调用 LLM 出题，自动审核化学方程式配平。"""
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
        }, ensure_ascii=False)

    except Exception as e:
        await provider.close()
        return json.dumps({"error": f"出题失败: {str(e)}", "questions": []}, ensure_ascii=False)


# ── 4. diagnose_barrier ──

async def diagnose_barrier(
    student_id: str = "",
    class_id: str = "",
) -> str:
    """诊断学生的化学学习障碍类型（概念理解/审题障碍/表述障碍）。传 student_id 做个体诊断，传 class_id 做班级诊断。"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    if student_id:
        row = session.execute(
            text("SELECT name, barrier_type, exercises_completed FROM students WHERE student_id = :sid"),
            {"sid": student_id},
        ).fetchone()
        session.close()

        if not row:
            return json.dumps({"error": f"学生 {student_id} 不存在"})

        barrier = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        dominant = max(barrier.items(), key=lambda x: x[1]) if barrier else ("unknown", 0)

        return json.dumps({
            "student_id": student_id,
            "student_name": row[0],
            "barrier_distribution": barrier,
            "dominant_barrier": dominant[0],
            "exercises_completed": row[2] or 0,
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

        return json.dumps({
            "class_id": class_id,
            "total_students": len(students),
            "barrier_distribution": {"concept": concept_count, "reading": reading_count, "expression": expression_count},
            "students": students[:10],
        }, ensure_ascii=False)

    session.close()
    return json.dumps({"error": "请提供 student_id 或 class_id"})


# ── 5. chemistry_tutor ──

async def chemistry_tutor(
    question: str = "",
    student_level: str = "中等",
) -> str:
    """回答学生的化学问题，引导式教学不直接给答案。适用于概念解释、解题思路引导、知识点讲解。"""
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
    """模拟高中化学实验，生成实验步骤、预测现象、写方程式、解释原理、提供安全提醒。"""
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
    """审核化学方程式是否配平，检查左右两侧各元素原子数量是否相等。"""
    from app.services.chemical_balance import audit_chemical_equation

    result = audit_chemical_equation(equation)
    return json.dumps(result, ensure_ascii=False)


# ── 8. weekly_report ──

async def weekly_report(student_id: str = "") -> str:
    """生成学生本周化学学习周报，包含学习内容、掌握情况、成长空间和家庭配合建议。通俗易懂，面向家长。"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from agent.provider.deepseek import DeepSeekProvider
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    student_row = session.execute(
        text("SELECT name, class_id, barrier_type, exercises_completed FROM students WHERE student_id = :sid"),
        {"sid": student_id},
    ).fetchone()

    if not student_row:
        session.close()
        return json.dumps({"error": f"学生 {student_id} 不存在"})

    student_name = student_row[0]
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

    prompt = f"""请为 {student_name} 生成本周化学学习报告:

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
        "student_name": student_name,
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
    """上传试卷PDF，自动提取化学题目并审核入库。返回提取数量、审核结果和入库状态。"""
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
    """为班级学生布置自适应练习。根据每个学生的障碍类型和最近发展区生成个性化化学题。"""
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
            return json.dumps({"error": f"班级 {class_id} 无学生"})

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

        return json.dumps({"assigned_count": len(assigned), "assigned": assigned}, ensure_ascii=False)
    finally:
        db.close()


# ── Tool list for factory ──

TOOLS = [
    search_exam_bank,
    web_search,
    generate_questions,
    diagnose_barrier,
    chemistry_tutor,
    simulate_experiment,
    balance_equation,
    weekly_report,
    import_exam_paper,
    assign_adaptive_practice,
]
