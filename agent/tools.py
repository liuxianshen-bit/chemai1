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
    """考试工作台 — 搜索历年高考化学真题（内部自动补齐：关键词→向量→联网）

    何时用：用户说"搜索真题""找高考题"等任何真题搜索意图时使用
    会发生什么：先关键词匹配本地题库，不够时向量召回补充，还不够时联网搜索补齐
    返回：已整理好的真题列表，已在返回文本中逐题列出全部题目，直接输出即可
    禁止：调完本工具后不要再调 web_search"""
    from app.services.exam_bank import exam_bank_service

    results = exam_bank_service.search_questions(
        knowledge_point=keyword or None,
        keyword=keyword or None,
        year=year if year else None,
        difficulty=difficulty or None,
        limit=limit,
        use_vector=True if keyword else False,
    )

    # ── Build display text and image metadata ──
    lines = []
    images = []

    if results:
        lines.append(f"## 来自题库（{len(results)} 道）\n")
        for i, q in enumerate(results, 1):
            lines.append(f"**第{i}题**  {q.source} 第{q.question_number}题")
            lines.append(f"知识点：{', '.join(q.knowledge_points)}  |  难度：{q.difficulty}")
            lines.append(f"> {q.content}")
            if q.options:
                lines.append(f"选项：{'；'.join(q.options)}")
            lines.append(f"答案：**{q.answer}**")
            if q.analysis:
                lines.append(f"解析：{q.analysis[:200]}")
            if q.page_image:
                import urllib.parse
                fig_url = "/static/figures/" + urllib.parse.quote(f"{q.region}/{q.year}/figures/{q.page_image}")
                lines.append(f"[原题图片见下方]")
                images.append({"q_index": i - 1, "title": f"第{i}题 原题图片", "urls": [fig_url]})
            lines.append("")

    # ── Web search supplement ──
    kw_count = getattr(results, 'keyword_count', len(results))
    web_lines = []
    if kw_count < 3 and keyword:
        try:
            web_result_str = await _do_web_search(keyword)
            web_data = json.loads(web_result_str)
            web_text = web_data.get("result", "")
            if web_text and len(web_text) > 50:
                web_lines.append(f"\n## AI辅助搜索（本地题库仅 {len(results)} 道，以下为AI补充，仅供教学参考。共补 {3 - len(results)} 道）\n")
                web_lines.append(web_text[:2000])
        except Exception:
            pass

    if web_lines:
        lines.append("---\n")
        lines.extend(web_lines)

    if not results and not web_lines:
        lines.append("未找到相关真题，建议尝试更简短的关键词")

    result_text = "\n".join(lines)
    result_text += "\n\n> 以上是全部搜索结果。已在上面逐题列出，直接输出即可，不要省略任何一题，不要额外添加知识点总结。"

    # Return structured format: LLM gets text, frontend gets images via SSE
    if images:
        return json.dumps({"text": result_text, "images": images}, ensure_ascii=False)
    return result_text


async def _do_web_search(query: str) -> str:
    """Internal web search helper — uses MiMo enable_search."""
    import os as _os, httpx as _httpx
    api_key = _os.getenv("XIAOMI_API_KEY", "")
    if not api_key:
        return json.dumps({"result": ""})

    try:
        async with _httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.xiaomimimo.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "mimo-v2.5",
                    "messages": [{"role": "user", "content": (
                        f"搜索关于「{query}」的高考化学真题。要求："
                        "1. 逐题列出，每道题必须包含：年份、省份/卷别、完整的题目内容、选项（如有）、标准答案、简要解析。"
                        "2. 如果搜不到原题，请明确说明'未搜到原题'，然后列出该知识点的典型考法和例题。"
                        "3. 禁止编造不存在的题目，你输出的每道题都应该是真实存在的高考真题。"
                    )}],
                    "enable_search": True, "max_tokens": 2048, "temperature": 0.1,
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({"result": data["choices"][0]["message"]["content"]})
    except Exception:
        pass
    return json.dumps({"result": ""})


# ── 2. web_search ──

async def web_search(query: str = "") -> str:
    """联网搜索 — 查询最新化学信息、高考动态、教学资源。也是真题搜索的兜底方案。

    何时用：
    - search_exam_bank 返回 NOT_FOUND → 调本工具搜索网上真题弥补
    - 用户明确要求"上网搜"、查询最新政策/新闻/大纲
    会发生什么：返回联网搜索结果摘要
    严格禁止：
    - 禁止在 search_exam_bank 返回 FOUND 后调用本工具
    - 禁止跳过 search_exam_bank 直接调本工具搜真题"""
    import os as _os, httpx as _httpx

    search_text = ""

    # Primary: MiMo with enable_search (has real web search capability)
    miimo_key = _os.getenv("XIAOMI_API_KEY", "")
    if miimo_key:
        try:
            async with _httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.xiaomimimo.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {miimo_key}", "Content-Type": "application/json"},
                    json={
                        "model": "mimo-v2.5",
                        "messages": [{"role": "user", "content": query}],
                        "enable_search": True, "max_tokens": 2048, "temperature": 0.3,
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                search_text = data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"MiMo search failed: {e}")

    # Fallback: Bing scraping (unreliable but no API key needed)
    if not search_text or len(search_text) < 50:
        import urllib.parse as _urlparse
        try:
            async with _httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://www.bing.com/search?q={_urlparse.quote(query)}",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
            if resp.status_code == 200:
                import re as _re
                snippets = _re.findall(r'<li class="b_algo"[^>]*>.*?</li>', resp.text, _re.DOTALL)
                if not snippets:
                    snippets = _re.findall(r'<p[^>]*>(.*?)</p>', resp.text, _re.DOTALL)
                parts = [_re.sub(r'<[^>]+>', '', s).strip()[:200] for s in snippets[:5]]
                search_text = "\n\n".join(p for p in parts if len(p) > 20)
        except Exception:
            pass

    if not search_text or len(search_text) < 20:
        return json.dumps({"error": "未获取到搜索结果，请稍后重试"}, ensure_ascii=False)

    # Summarize with DeepSeek
    ds_key = _os.getenv("DEEPSEEK_API_KEY", "")
    if ds_key and len(search_text) > 100:
        try:
            async with _httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {ds_key}", "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "用简洁中文总结以下搜索结果，列出关键信息。不超过400字。"},
                            {"role": "user", "content": f"搜索词: {query}\n\n搜索结果:\n{search_text[:3000]}"},
                        ],
                        "max_tokens": 1024, "temperature": 0.3,
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                result = data["choices"][0]["message"]["content"]
                return json.dumps({
                    "query": query,
                    "result": result,
                }, ensure_ascii=False)
        except Exception:
            pass

    return json.dumps({
        "query": query,
        "result": search_text[:2000],
    }, ensure_ascii=False)


# ── 化学式后处理：确保 LaTeX 格式一致 ──

def _normalize_chem_formulas(text: str) -> str:
    """归一化化学式格式：
    1. 将 $...$ 内部的 → 替换为 \\rightarrow
    2. 检测裸化学式（如 Cl2, Fe3+）并在必要时包装
    """
    import re

    # Step 1: 修复 $...$ 内部的 → 为 \\rightarrow
    def _fix_arrow_in_math(m: re.Match) -> str:
        content = m.group(1)
        content = content.replace("→", "\\rightarrow")
        content = content.replace("⇌", "\\rightleftharpoons")
        content = content.replace("↑", "\\uparrow")
        content = content.replace("↓", "\\downarrow")
        return f"${content}$"

    text = re.sub(r"\$([^$]+)\$", _fix_arrow_in_math, text)

    # Step 2: 如果整段文本零 $ 但含有明显的化学式模式 → 用正则包装
    if "$" not in text:
        # 匹配至少2个元素符号组成的化学式（单元素如 Na 不处理，避免误伤）
        # 如: H2O, CO2, NaCl, NaOH, Fe2O3, Na2CO3
        chem_pattern = re.compile(
            r'\b([A-Z][a-z]?\d*[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*)'
        )
        # 常见化学式白名单
        known_formulas = {
            "H2O", "CO2", "NaCl", "NaOH", "HCl", "Fe2O3", "FeO", "CaCO3",
            "NH4Cl", "NH3", "Cl2", "Na", "Fe", "Cu", "O2", "H2", "N2",
            "SO2", "SO3", "H2SO4", "CuSO4", "FeSO4", "CaO", "MnO2",
            "KClO3", "KCl", "Na2CO3", "FeCl3", "CuO", "MgO", "Al2O3",
            "NO2", "NO", "CO", "CH4", "C2H5OH", "CH3COOH", "HNO3",
            "H3PO4", "Na2SO4", "BaSO4", "AgCl", "AgNO3", "CaCl2",
            "Fe(OH)3", "Al(OH)3", "Mg(OH)2", "Ca(OH)2", "NaOH",
            "NaHCO3", "KMnO4", "K2Cr2O7",
        }
        def _wrap_chem(m: re.Match) -> str:
            w = m.group(0)
            # Skip if looks like English word (3+ consecutive lowercase letters)
            if re.search(r'[a-z]{3,}', w):
                return w
            # Must be in whitelist or contain digits
            if w in known_formulas or any(c.isdigit() for c in w):
                # 转换数字下标: Cl2 → Cl_2, Fe2O3 → Fe_2O_3
                subbed = re.sub(r'([A-Za-z)])(\d+)', r'\1_\2', w)
                return f"${subbed}$"
            return w
        text = chem_pattern.sub(_wrap_chem, text)

    return text


# ── 3. generate_questions ──

async def generate_questions(
    knowledge_points: str = "",
    difficulty: str = "medium",
    quantity: int = 5,
    question_types: str = "",
    variant_qid: str = "",
    variant_source: str = "",
) -> str:
    """AI出题 — 根据参数直接生成题目

    何时用：用户明确说了知识点+题型+数量（如"出5道氧化还原选择题"），参数齐全直接出题
    会发生什么：调用 LLM 生成题目（选择题带选项，填空题用___标记，计算题含分步解答），
              运行方程式审核，返回题目列表并在对话中展示考试工作台面板
    下一步：用户可要求修改题目、保存到题库（save_to_bank）或重出
    NOT for 参数不全 — 用 show_exam_workbench 打开面板让用户补全
    question_types 格式："single_choice:3,fill_blank:2,calculation:1"
    """
    import re, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    # Parse knowledge points
    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]
    if not kps:
        kps = ["高中化学综合"]

    # Parse question types: "single_choice:3,fill_blank:2" → [{val, qty}, ...]
    type_map_reverse = {
        "single_choice": "choice", "fill_blank": "fill",
        "calculation": "calc", "experiment": "experiment", "inference": "inference",
    }
    types = []
    total_qty = quantity
    if question_types:
        for item in question_types.split(","):
            parts = item.strip().split(":")
            if len(parts) == 2:
                val, qty = parts[0].strip(), int(parts[1].strip())
                types.append({"val": val, "qty": qty})
        total_qty = sum(t["qty"] for t in types)

    # Map to llm_service format
    llm_types = [type_map_reverse.get(t["val"], "choice") for t in types] if types else ["choice"]

    # Build RAG context (blueprint or vector search)
    from app.services.exam_bank import exam_bank_service
    rag_context = []
    if variant_qid:
        blueprint_q = exam_bank_service.get_by_exam_id(variant_qid)
        if blueprint_q:
            rag_context = [{
                "content": blueprint_q.content,
                "answer": blueprint_q.answer,
                "knowledge_points": blueprint_q.knowledge_points,
                "difficulty": blueprint_q.difficulty,
                "source": blueprint_q.source,
                "exam_id": blueprint_q.exam_id,
                "similarity": 1.0,
                "match_method": "blueprint",
            }]
    else:
        similar = exam_bank_service.find_similar_questions(
            knowledge_points=kps, difficulty=difficulty, limit=3,
        )
        if similar:
            rag_context = [{
                "content": q.content, "answer": q.answer,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty, "source": q.source,
                "exam_id": q.exam_id, "similarity": 0.8, "match_method": "simple",
            } for q in similar]

    # Generate via llm_service (same engine as the REST endpoint)
    from app.services.llm_service import llm_service
    result = llm_service.generate_questions(
        knowledge_points=kps,
        difficulty=difficulty,
        quantity=total_qty,
        question_types=llm_types,
        rag_context=rag_context if rag_context else None,
    )

    questions = []
    if result.get("success") and "questions" in result.get("content", ""):
        try:
            content = result["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            data = json.loads(content)
            questions = data.get("questions", [])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    if not questions:
        return json.dumps({
            "result": f"已尝试生成{total_qty}道题但未获得有效结果，请检查知识点设置或重试",
            "total": 0,
            "questions": [],
        }, ensure_ascii=False)

    # Normalize chemical formula formatting (LaTeX consistency)
    for q in questions:
        for field in ("content", "answer"):
            if field in q and q[field]:
                q[field] = _normalize_chem_formulas(q[field])
        if "options" in q and q["options"]:
            q["options"] = [_normalize_chem_formulas(o) for o in q["options"]]

    # Audit equations
    from app.services.chemical_balance import audit_chemical_equation
    for q in questions:
        if any(kw in q.get("content", "") for kw in ["→", "=", "->", "方程式", "反应"]):
            eq_match = re.search(r"([\d\w\(\)\+\s→=->]+)", q.get("content", ""))
            if eq_match:
                audit_chemical_equation(eq_match.group(1))

    return json.dumps({
        "result": f"已生成 {len(questions)} 道题目",
        "total": len(questions),
        "questions": questions,
        "knowledge_points": kps,
        "difficulty": difficulty,
        "_component": {
            "component": "exam-workbench",
            "params": {
                "knowledge_points": kps,
                "difficulty": difficulty,
                "types": types,
                "variant_source": variant_source,
                "questions": questions,
            },
        },
    }, ensure_ascii=False)


# ── 4. diagnose_barrier ──

async def diagnose_barrier(
    student_id: str = "",
    student_name: str = "",
    class_id: str = "",
) -> str:
    """学情诊断 — 诊断学生的化学学习障碍类型（概念理解/审题障碍/表述障碍）

    何时用：用户询问某个学生或班级的学习情况、错题原因、薄弱环节
    会发生什么：个体诊断返回学生障碍分布和主导障碍类型；班级诊断返回全班障碍分布统计
    下一步：个体诊断 → 根据障碍类型推荐针对性练习（assign_adaptive_practice）；班级诊断 → 跳转诊断页面展示图表
    NOT for 在聊天中展示诊断图表 — 用 show_diagnosis
    NOT for 生成周报/学习报告 — 用 weekly_report"""
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

        result_data = {
            "student_id": student_id,
            "student_name": row[0],
            "barrier_distribution": barrier,
            "dominant_barrier": dominant[0],
            "exercises_completed": row[2] or 0,
            "_route": {"navigate": False},
        }

        # Writeback to long-term memory (best-effort)
        _writeback_diagnosis(student_id, result_data)

        return json.dumps(result_data, ensure_ascii=False)

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
    persona: str = "tutor",
) -> str:
    """聊天辅导 — 根据角色提供教学辅导或教研分析

    何时用：用户提问化学概念、解题思路、知识点讲解、教研分析等非出题类问题
    会发生什么：教师→教研分析（考点分布、教学策略、学生常见误区）；学生→引导式教学
    下一步：如用户仍有疑问 → 继续解答
    NOT for 实验步骤/现象 — 用 simulate_experiment
    NOT for 检查方程式配平 — 用 balance_equation"""
    from agent.provider.deepseek import DeepSeekProvider

    provider = DeepSeekProvider()

    print(f"[DEBUG] chemistry_tutor called: persona={persona}, question={question[:50]}", flush=True)
    if not persona or persona == "auto" or persona == "tutor":
        try: from agent.langgraph_agent import _current_persona; persona = _current_persona
        except: pass
    if persona == "teacher":
        system_prompt = """你是高中化学教研助手，正在协助一位化学教师备课和教研。

回答原则：
1. 专业深度：提供高考考点分布、命题趋势、评分标准等教研级信息
2. 教学策略：给出课堂讲解思路、实验演示建议、习题设计方向
3. 学生误区：列举该知识点的常见错误认知和纠正方法
4. 效率优先：直接给出结构化分析，不要反问教师基础问题
5. 教辅联动：如涉及具体题目可建议打开考试工作台出题
6. 单次回复不超过800字"""
    else:
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
    下一步：基于实验结果回答用户追问；如需配平实验方程式 → balance_equation
    NOT for 一般化学概念讲解 — 用 chemistry_tutor"""
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
    下一步：如配平正确 → 告知用户；如有问题 → 指出不平衡的元素和修正建议
    NOT for 化学原理讲解/概念解释 — 用 chemistry_tutor"""
    from app.services.chemical_balance import audit_chemical_equation

    result = audit_chemical_equation(equation)
    return json.dumps(result, ensure_ascii=False)


# ── 8. weekly_report ──

async def weekly_report(student_id: str = "", student_name: str = "", class_name: str = "") -> str:
    """学习报告 — 生成学生或班级的化学学习周报

    何时用：用户（通常为家长或老师）要求查看学习报告、本周学习情况
    会发生什么：个人报告包含学习内容、掌握情况、成长空间和家庭配合建议；班级报告包含整体统计
    下一步：个人报告 → 对话中展示；班级报告 → 可跳转诊断页面查看图表
    NOT for 查薄弱环节/学情分析/障碍分布 — 用 diagnose_barrier"""
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


# ── 9. assign_adaptive_practice ──

async def assign_adaptive_practice(
    class_id: str = "",
    knowledge_points: str = "",
    question_count: int = 5,
) -> str:
    """自适应练习 — 根据学生障碍类型布置个性化练习

    何时用：诊断完成后，老师要求给班级/学生布置针对性练习
    会发生什么：为每个学生生成符合其最近发展区的个性化化学题，自动分配
    下一步：分配完成 → 告知老师分配结果；⚠ 此工具需要先调 request_approval 确认
    """
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

    何时用：用户在考试工作台面板中出题完成后保存
    会发生什么：创建题库文件夹（自动命名），将题目存入数据库，可在考试工作台中管理和复用
    下一步：保存后告知用户文件夹名，引导用户去考试工作台查看 → 页面跳转到 exam-v2 题库 tab
    NOT for 出题 — 先调 show_exam_workbench 让用户出题，出完再保存"""
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

        # Sync to exam_bank_service memory + ChromaDB vector index
        try:
            from app.services.exam_bank import exam_bank_service
            from app.models.historical_exam import HistoricalQuestion
            from app.services.vector_search import vector_search_service

            for i, q in enumerate(q_list):
                hq = HistoricalQuestion(
                    exam_id=question_id if i == 0 else f"q_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}",
                    source="AI生成",
                    year=None,
                    region="AI生成",
                    paper_name=set_name,
                    question_number=str(i + 1),
                    original_number=str(i + 1),
                    question_type=q.get("type", "single_choice"),
                    content=q.get("content", ""),
                    options=q.get("options"),
                    answer=str(q.get("answer", "")),
                    analysis=q.get("analysis", ""),
                    knowledge_points=q.get("knowledge_points", []),
                    difficulty=q.get("difficulty", "medium"),
                    discrimination=0.5,
                    score=0,
                    chapter="",
                    page_image=None,
                )
                exam_bank_service.add_question(hq)

            # Incrementally index to ChromaDB
            idx_data = [{
                "exam_id": q.get("content", "")[:20] + str(i),
                "content": q.get("content", ""),
                "knowledge_points": q.get("knowledge_points", []),
                "difficulty": q.get("difficulty", "medium"),
                "source": "AI生成",
                "year": None,
                "region": "AI生成",
            } for i, q in enumerate(q_list)]
            if idx_data:
                vector_search_service.index_questions(idx_data, mode="append")
        except Exception as e:
            print(f"Exam bank/vector sync skipped: {e}")

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
    NOT for 先搜真题再问要不要出题 — 直接调此工具，不要调 search_exam_bank"""
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
    NOT for 只需要原始障碍数据不需要图表 — 用 diagnose_barrier
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
    NOT for 搜索题库里面的题目内容 — 用 search_exam_bank
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
    ⚠ 此操作不可逆，需要先调 request_approval 确认
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
    NOT for 查某个学生或班级的障碍数据 — 用 diagnose_barrier
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

# ── Diagnosis writeback helper ──

def _writeback_diagnosis(student_id: str, result_data: dict):
    """Best-effort write diagnosis result to SqliteStore."""
    try:
        store = _get_store_context()
        if not store:
            return
        import asyncio
        from datetime import datetime

        async def _write():
            ns = ("student", student_id, "diagnosis")
            # Upsert: keep max 5 entries
            try:
                existing = await store.asearch(ns, limit=5)
                if existing and len(existing) >= 5:
                    oldest = existing[-1]
                    oldest_key = getattr(oldest, "key", "")
                    if oldest_key:
                        await store.adelete(ns, oldest_key)
            except Exception:
                pass
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            await store.aput(ns, f"diag_{ts}", {
                "barrier_type": result_data.get("dominant_barrier"),
                "barrier_distribution": result_data.get("barrier_distribution"),
                "timestamp": ts,
            })

        # Run async write in current event loop if available
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_write())
        except RuntimeError:
            pass
    except Exception:
        pass


# ── 15. memory_student_get ──

async def memory_student_get(
    student_id: str = "",
    memory_type: str = "all",
) -> str:
    """学情记忆 — 获取学生历史诊断和学习计划记忆

    何时用: 教师询问某学生的学习历史、之前的诊断结果、薄弱环节变化趋势
    会发生什么: 返回学生诊断历史(最多5条)和当前学习计划
    """
    store = _get_store_context()
    if not store:
        return json.dumps({"error": "记忆系统不可用"}, ensure_ascii=False)

    results = {"student_id": student_id, "diagnoses": [], "learning_plan": None}

    if student_id:
        # Diagnosis history
        ns = ("student", student_id, "diagnosis")
        try:
            items = await store.asearch(ns, limit=5)
            results["diagnoses"] = [
                {"key": getattr(i, "key", ""), "data": getattr(i, "value", i)}
                for i in (items or [])
            ]
        except Exception:
            pass

        # Current learning plan
        ns2 = ("student", student_id, "learning_plan")
        try:
            plan = await store.aget(ns2, "current")
            if plan and hasattr(plan, "value"):
                results["learning_plan"] = plan.value
        except Exception:
            pass

    return json.dumps(results, ensure_ascii=False)


# ── 16. memory_teacher_get ──

async def memory_teacher_get(
    teacher_id: str = "",
) -> str:
    """教师偏好 — 获取教师教学偏好和历史设置

    何时用: 需要了解教师的教学风格、难度偏好、班级配置
    会发生什么: 返回教师存储的偏好设置
    """
    store = _get_store_context()
    if not store:
        return json.dumps({"error": "记忆系统不可用"}, ensure_ascii=False)

    prefs = {}
    if teacher_id:
        try:
            item = await store.aget(("teacher", teacher_id, "preferences"), "current")
            if item and hasattr(item, "value"):
                prefs = item.value
        except Exception:
            pass

    return json.dumps(prefs, ensure_ascii=False)


def _get_store_context():
    """Get SqliteStore from agent context."""
    try:
        from agent.langgraph_agent_v2 import get_store_context
        return get_store_context()
    except Exception:
        return None


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
    assign_adaptive_practice,
    save_to_bank,
    list_banks,
    delete_bank,
    memory_student_get,
    memory_teacher_get,
]
