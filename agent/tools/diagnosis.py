"""Diagnosis tools — barrier diagnosis, student listing, weekly reports, adaptive practice."""

import json
import re

from dotenv import load_dotenv
load_dotenv()


def _safe_barrier(raw) -> dict:
    """Parse barrier_type from DB into a dict, handling all edge cases."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            if isinstance(val, dict):
                return val
            return {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _dominant(barrier: dict) -> tuple:
    """Get dominant barrier type and score. Returns ('unknown', 0) on empty."""
    if not barrier:
        return ("unknown", 0)
    try:
        return max(barrier.items(), key=lambda x: x[1])
    except (ValueError, AttributeError):
        return ("unknown", 0)


# ═══════════════════════════════════════════════════════════════════════
# diagnose_barrier
# ═══════════════════════════════════════════════════════════════════════

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
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

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

        if not row:
            session.close()
            return json.dumps({"error": f"学生 {student_id} 不存在", "_route": {"navigate": False}})

        barrier = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        dominant = _dominant(barrier) if barrier else ("unknown", 0)

        # 答题统计
        stats = session.execute(
            text("SELECT COUNT(*), SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) FROM student_answers WHERE student_id = :sid"),
            {"sid": student_id},
        ).fetchone()
        total_answers = stats[0] or 0
        correct_answers = stats[1] or 0
        accuracy = round(correct_answers / total_answers, 2) if total_answers > 0 else 0

        # 薄弱知识点 (从错题中提取)
        weak_kps = []
        wrong_rows = session.execute(
            text("SELECT q.knowledge_points FROM student_answers sa JOIN questions q ON sa.question_id = q.question_id WHERE sa.student_id = :sid AND sa.is_correct = 0 ORDER BY sa.answered_at DESC LIMIT 30"),
            {"sid": student_id},
        ).fetchall()
        kp_counter = {}
        for (kps_json,) in wrong_rows:
            if kps_json:
                kps = json.loads(kps_json) if isinstance(kps_json, str) else kps_json
                for kp in kps:
                    kp_counter[kp] = kp_counter.get(kp, 0) + 1
        weak_kps = sorted(kp_counter.items(), key=lambda x: -x[1])[:5]

        # 成绩趋势 — 和學生详情页一致：按时间排序的滚动累计正确率
        score_trend = []
        act_rows = session.execute(
            text("SELECT sa.is_correct, sa.answered_at FROM student_answers sa WHERE sa.student_id = :sid ORDER BY sa.answered_at ASC"),
            {"sid": student_id},
        ).fetchall()
        correct = 0
        total = 0
        for is_correct, answered_at in act_rows:
            total += 1
            if is_correct:
                correct += 1
            date_str = answered_at[:10] if isinstance(answered_at, str) and len(answered_at) > 10 else (answered_at.strftime("%m-%d") if hasattr(answered_at, 'strftime') else str(answered_at)[:10])
            score_trend.append({
                "date": date_str,
                "cumulative_rate": round(correct / total, 2) if total > 0 else 0,
                "correct": correct,
                "total": total,
            })

        # Downsample to max 20 points for rendering
        if len(score_trend) > 20:
            step = len(score_trend) / 20
            score_trend = [score_trend[int(i * step)] for i in range(20)]

        session.close()

        result_data = {
            "student_id": student_id,
            "student_name": row[0],
            "barrier_distribution": barrier,
            "dominant_barrier": dominant[0],
            "exercises_completed": row[2] or 0,
            "total_answers": total_answers,
            "correct_answers": correct_answers,
            "accuracy": accuracy,
            "weak_knowledge_points": [{"name": k, "errors": c} for k, c in weak_kps],
            "score_trend": score_trend,
            "_route": {"navigate": False},
            "_component": {"component": "diagnosis", "params": {
                "student_id": student_id,
                "student_name": row[0],
                "barrier_distribution": barrier,
                "dominant_barrier": dominant[0],
                "exercises_completed": row[2] or 0,
                "total_answers": total_answers,
                "correct_answers": correct_answers,
                "accuracy": accuracy,
                "weak_knowledge_points": [{"name": k, "errors": c} for k, c in weak_kps],
                "score_trend": score_trend,
            }},
        }

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
                    "student_id": row[0], "student_name": row[1],
                    "dominant": _dominant(barrier)[0],
                })
                for bt, val in _safe_barrier(barrier).items():
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
            "_component": {"component": "diagnosis", "params": _data},
        }, ensure_ascii=False)

    session.close()
    return json.dumps({"error": "请提供 student_id 或 class_id", "_route": {"navigate": False}})


# ═══════════════════════════════════════════════════════════════════════
# show_diagnosis
# ═══════════════════════════════════════════════════════════════════════

async def show_diagnosis(student_id: str = "", student_name: str = "", class_id: str = "") -> str:
    """学情诊断 — 在聊天中展示诊断结果和图表

    何时用：用户要求查看学生或班级的诊断结果
    会发生什么：在聊天中渲染诊断面板，包含障碍分布图和关键指标
    下一步：用户可点击"针对出题"快捷按钮，跳转到出题面板
    NOT for 只需要原始障碍数据不需要图表 — 用 diagnose_barrier"""
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
        "_component": {"component": "diagnosis", "params": data},
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# show_students
# ═══════════════════════════════════════════════════════════════════════

async def show_students(
    class_id: str = "",
    class_name: str = "",
    student_name: str = "",
    filter_barrier: str = "",
) -> str:
    """学生/班级列表 — 展示班级学生或全部班级

    何时用：用户问"有几个班""有哪些学生""找问题大的学生""班里谁最薄弱""找下李雨萱"
    会发生什么：指定学生姓名时按姓名模糊搜索学生；指定班级时列出班级学生；都不指定时列出所有班级
    下一步：用户点击学生卡片 → 触发该学生的诊断
    NOT for 不需要搜索学生只需要诊断数据 — 用 diagnose_barrier
    NOT for 查某个学生或班级的障碍数据 — 用 diagnose_barrier"""
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    # ── student_name search: fuzzy match on student name ──
    if student_name:
        rows = session.execute(
            text("SELECT s.student_id, s.name, s.barrier_type, s.exercises_completed, c.name as class_name "
                 "FROM students s LEFT JOIN classes c ON s.class_id = c.class_id "
                 "WHERE s.name LIKE :n ORDER BY s.exercises_completed ASC"),
            {"n": f"%{student_name}%"},
        ).fetchall()
        session.close()

        if not rows:
            return json.dumps({"message": f"未找到名为 '{student_name}' 的学生", "_component": None}, ensure_ascii=False)

        barrier_labels = {"concept": "概念理解", "reading": "审题仔细度", "expression": "答题表述", "unknown": "未诊断"}
        students = []
        for r in rows:
            barrier = r[2] or {}
            if isinstance(barrier, str):
                try: barrier = json.loads(barrier)
                except Exception: barrier = {}
            if not isinstance(barrier, dict) or not barrier:
                dominant = ("unknown", 0)
            else:
                try: dominant = _dominant(barrier)
                except Exception: dominant = ("unknown", 0)
            students.append({
                "student_id": r[0], "name": r[1],
                "dominant_barrier": dominant[0],
                "barrier_score": round(dominant[1], 2),
                "exercises_completed": r[3] or 0,
                "class_name": r[4] or "",
            })

        summary = f"找到 {len(students)} 名匹配 '{student_name}' 的学生：" + "、".join(
            f"{s['name']}({barrier_labels.get(s['dominant_barrier'], s['dominant_barrier'])})" for s in students[:10]
        )
        return json.dumps({
            "result": summary,
            "student_count": len(students),
            "students": students,
            "_component": {
                "component": "student-list",
                "params": {"students": students, "search_term": student_name},
            },
        }, ensure_ascii=False)

    if class_name and not class_id:
        cn = str.maketrans("一二三四五六七八九十", "1234567890")

        row = session.execute(
            text("SELECT class_id, name FROM classes WHERE name = :n"),
            {"n": class_name},
        ).fetchone()

        if not row:
            row = session.execute(
                text("SELECT class_id, name FROM classes WHERE name LIKE :n"),
                {"n": f"%{class_name}%"},
            ).fetchone()

        if not row:
            clean = class_name.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
            m = re.match(r"(.+)([一二三四五六七八九十\d]+)\s*班", clean)
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
        rows = session.execute(
            text("SELECT class_id, name, grade, student_count FROM classes ORDER BY name")
        ).fetchall()
        session.close()
        if not rows:
            return json.dumps({"result": "暂无班级数据"}, ensure_ascii=False)
        classes = [{"class_id": r[0], "name": r[1], "grade": r[2], "student_count": r[3] or 0} for r in rows]
        summary = "共" + str(len(classes)) + "个班级：" + "、".join(c["name"] + "(" + str(c["student_count"]) + "人)" for c in classes)
        return json.dumps({"result": summary, "classes": classes, "total": len(classes)}, ensure_ascii=False)

    cls_row = session.execute(
        text("SELECT name FROM classes WHERE class_id = :cid"), {"cid": class_id}
    ).fetchone()
    resolved_class_name = cls_row[0] if cls_row else class_id

    rows = session.execute(
        text("SELECT student_id, name, barrier_type, exercises_completed FROM students WHERE class_id = :cid ORDER BY exercises_completed ASC"),
        {"cid": class_id},
    ).fetchall()
    session.close()

    if not rows:
        return json.dumps({"message": f"{resolved_class_name} 暂无学生", "_component": None}, ensure_ascii=False)

    students = []
    for r in rows:
        barrier = _safe_barrier(r[2])
        if barrier:
            dominant = _dominant(barrier)
            barrier_type = dominant[0]
            barrier_score = dominant[1]
        else:
            barrier_type = "unknown"
            barrier_score = 0

        if filter_barrier:
            bt_map = {"计算": "concept", "概念": "concept", "审题": "reading", "阅读": "reading", "表述": "expression", "表达": "expression"}
            target = bt_map.get(filter_barrier, filter_barrier)
            if barrier_type != target:
                continue

        students.append({
            "student_id": r[0], "name": r[1],
            "dominant_barrier": barrier_type,
            "barrier_score": round(barrier_score, 2),
            "exercises_completed": r[3] or 0,
        })

    if filter_barrier and not students:
        return json.dumps({"message": f"{resolved_class_name} 没有 {filter_barrier} 障碍的学生", "_component": None}, ensure_ascii=False)

    students.sort(key=lambda s: s["barrier_score"], reverse=True)

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
            "params": {"class_name": resolved_class_name, "class_id": class_id, "students": students},
        },
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# weekly_report
# ═══════════════════════════════════════════════════════════════════════

async def weekly_report(student_id: str = "", student_name: str = "", class_name: str = "") -> str:
    """学习报告 — 生成学生或班级的化学学习周报

    何时用：用户（通常为家长或老师）要求查看学习报告、本周学习情况
    会发生什么：个人报告包含学习内容、掌握情况、成长空间和家庭配合建议；班级报告包含整体统计
    下一步：个人报告 → 对话中展示；班级报告 → 可跳转诊断页面查看图表
    NOT for 查薄弱环节/学情分析/障碍分布 — 用 diagnose_barrier"""
    from agent.provider.deepseek import DeepSeekProvider
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

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
        temperature=0.7, max_tokens=512,
    )

    await provider.close()

    return json.dumps({
        "student_name": student_name_resolved,
        "report": result.content,
        "exam_count": exam_count,
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# assign_adaptive_practice
# ═══════════════════════════════════════════════════════════════════════

async def assign_adaptive_practice(
    class_id: str = "",
    knowledge_points: str = "",
    question_count: int = 5,
) -> str:
    """自适应练习 — 根据学生障碍类型布置个性化练习

    何时用：诊断完成后，老师要求给班级/学生布置针对性练习题
    会发生什么：为每个学生生成符合其最近发展区的个性化化学题，自动分配
    下一步：分配完成 → 告知老师分配结果；⚠ 此工具需要先调 request_approval 确认
    NOT for 生成学习计划/学习方案/学习规划 — 用 generate_learning_plan"""
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
                    "student_name": student.name, "zpd_difficulty": zpd,
                    "barrier": barrier, "question_count": question_count, "weak_kps": weak,
                })

        return json.dumps({"assigned_count": len(assigned), "assigned": assigned, "_route": {"navigate": False}}, ensure_ascii=False)
    finally:
        db.close()


# ── generate_learning_plan ──

async def generate_learning_plan(
    student_id: str = "",
    student_name: str = "",
) -> str:
    """学习计划 — 为指定学生打开学习方案编辑器（跳到学生管理页）

    何时用：教师说"生成学习计划""给XX做一份学习方案""帮XX规划学习""制定学习计划"
    会发生什么：直接打开学生管理页面，自动弹出该学生的详情抽屉并触发方案生成。
               教师可在弹窗中编辑、保存、发送，体验与学生管理页完全一致。
    返回：页面跳转，无需在聊天中渲染
    ⚠ NOT for 出题/布置练习/做题/针对性训练 — 用 assign_adaptive_practice
    ⚠ NOT for 查障碍/诊断数据 — 用 diagnose_barrier"""
    # Resolve student_id from name if needed
    if student_name and not student_id:
        from app.models.database import get_db
        from sqlalchemy import text
        session = next(get_db())
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_name}%"},
        ).fetchall()
        session.close()
        if not rows:
            return json.dumps({"error": f"未找到名为 '{student_name}' 的学生", "_route": {"navigate": False}})
        if len(rows) > 1:
            candidates = [{"student_id": r[0], "name": r[1]} for r in rows]
            return json.dumps({"multiple_matches": candidates, "hint": "找到多个匹配学生，请指定学号", "_route": {"navigate": False}})
        student_id = rows[0][0]
        student_name_resolved = rows[0][1]
    else:
        student_name_resolved = student_name

    if not student_id:
        return json.dumps({"error": "请提供 student_id 或 student_name", "_route": {"navigate": False}})

    return json.dumps({
        "message": f"正在为 {student_name_resolved or student_id} 打开学习方案编辑器…",
        "_route": {"navigate": True, "page": "students", "params": {"focus": student_id, "action": "plan"}},
    }, ensure_ascii=False)


# ── send_learning_plan ──

async def send_learning_plan(
    student_id: str = "",
    plan_data: str = "",
) -> str:
    """发送学习计划 — 将确认后的计划发送给学生

    何时用：教师在聊天中确认计划无误后，说"发送""发给学生""推送给XX"
    会发生什么：持久化到 SqliteStore 长期记忆, 学生端刷新即可查看
    返回：确认消息, 含学生姓名和发送时间
    NOT for 生成计划 — 用 generate_learning_plan"""
    if not student_id:
        return json.dumps({"error": "请提供 student_id"}, ensure_ascii=False)

    # Parse plan_data if provided as JSON string
    plan_payload = {}
    if plan_data:
        try:
            plan_payload = json.loads(plan_data) if isinstance(plan_data, str) else plan_data
        except (json.JSONDecodeError, TypeError):
            plan_payload = {"raw_plan": str(plan_data)[:1000]}

    import httpx as _httpx
    api_base = "http://127.0.0.1:8000"
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{api_base}/api/diagnosis/learning-plan/apply/{student_id}",
                json=plan_payload if plan_payload else {},
            )
        if resp.status_code == 404:
            return json.dumps({"error": f"学生 {student_id} 不存在"}, ensure_ascii=False)
        if resp.status_code != 200:
            return json.dumps({"error": f"发送失败: HTTP {resp.status_code}"}, ensure_ascii=False)
        data = resp.json()
    except Exception as e:
        return json.dumps({"error": f"发送请求失败: {str(e)}"}, ensure_ascii=False)

    return json.dumps({
        "result": data.get("message", "学习计划已发送"),
        "student_id": student_id,
        "student_name": data.get("student_name", ""),
    }, ensure_ascii=False)


# ── generate_parent_report ──

async def generate_parent_report(
    student_name: str = "",
    student_id: str = "",
) -> str:
    """家长报告生成 — 为指定学生生成面向家长的完整学习报告预览

    何时用：教师说"发报告给XX家长""把XX的学习报告发给家长""给家长发学习报告"
    会发生什么：聚合练习数据、障碍诊断、知识点掌握，生成家长可读报告预览，在聊天中展示
    返回：报告预览卡片，教师可要求修改或确认后发送
    下一步：教师确认后调 send_report_to_parent 发送
    NOT for 直接发送 — 必须先预览确认"""
    from app.models.database import get_db
    from sqlalchemy import text

    # Resolve student
    session = next(get_db())
    if student_name and not student_id:
        rows = session.execute(
            text("SELECT student_id, name FROM students WHERE name LIKE :n"),
            {"n": f"%{student_name}%"},
        ).fetchall()
        if not rows:
            session.close()
            return json.dumps({"error": f"未找到名为 '{student_name}' 的学生"}, ensure_ascii=False)
        if len(rows) > 1:
            session.close()
            return json.dumps({"error": f"找到 {len(rows)} 个匹配学生, 请指定学号"}, ensure_ascii=False)
        student_id = rows[0][0]

    row = session.execute(
        text("SELECT s.name, s.barrier_type, s.exercises_completed, s.class_id, c.name "
             "FROM students s LEFT JOIN classes c ON s.class_id=c.class_id WHERE s.student_id=:sid"),
        {"sid": student_id},
    ).fetchone()
    if not row:
        session.close()
        return json.dumps({"error": f"学生 {student_id} 不存在"}, ensure_ascii=False)

    sname = row[0]
    barrier = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
    ex_count = row[2] or 0
    class_name = row[4] or ""

    # Get practice stats from student_answers (this week)
    from datetime import datetime as _dt, timedelta as _td
    week_start = _dt.utcnow() - _td(days=7)
    week_answers = session.execute(
        text("SELECT is_correct FROM student_answers WHERE student_id=:sid AND answered_at >= :ws"),
        {"sid": student_id, "ws": week_start},
    ).fetchall()
    total_w = len(week_answers)
    correct_w = sum(1 for a in week_answers if a[0])

    # Weak knowledge points
    from collections import Counter
    kp_counter = Counter()
    wrong_answers = session.execute(
        text("SELECT question_id FROM student_answers WHERE student_id=:sid AND is_correct=0 ORDER BY answered_at DESC LIMIT 30"),
        {"sid": student_id},
    ).fetchall()
    for (qid,) in wrong_answers:
        q = session.execute(text("SELECT knowledge_points FROM questions WHERE question_id=:q"), {"q": qid}).fetchone()
        if q and q[0]:
            kps = json.loads(q[0]) if isinstance(q[0], str) else q[0]
            for kp in kps:
                kp_counter[kp] += 1
    weak_kps = [{"name": kp, "errors": c} for kp, c in kp_counter.most_common(5)]

    # Barrier labels
    barrier_labels = {"concept": "概念理解", "reading": "审题仔细度", "expression": "答题表述"}
    dominant = _dominant(barrier) if barrier else ("concept", 0)
    dom_label = barrier_labels.get(dominant[0], dominant[0])

    # Suggestions based on barrier
    suggestions = {
        "concept": "建议帮孩子建立知识框架图，用思维导图梳理化学概念之间的联系。",
        "reading": "建议每天陪孩子读一道题，让他把「题目给了什么条件」说出来。",
        "expression": "鼓励孩子写完整的解题过程，化学符号和方程式要写规范。",
    }

    session.close()

    accuracy = round(correct_w / total_w * 100) if total_w > 0 else 0
    report = {
        "student_name": sname,
        "class_name": class_name,
        "exercises_completed": ex_count,
        "week_practice_count": total_w,
        "week_accuracy": accuracy,
        "dominant_barrier": dom_label,
        "barrier_distribution": barrier,
        "weak_knowledge_points": weak_kps,
        "suggestion": suggestions.get(dominant[0], "多鼓励孩子，关注学习过程而非分数。"),
    }

    # Format preview
    kp_text = "、".join(f"{k['name']}({k['errors']}次)" for k in weak_kps[:5]) if weak_kps else "暂无薄弱数据"
    preview = (
        f"📋 **{sname} · 家长学习报告 (预览)**\n\n"
        f"📊 本周完成 {total_w} 道练习，正确率 {accuracy}%\n"
        f"🎯 薄弱知识点: {kp_text}\n"
        f"🧠 主要学习特点: {dom_label} ({int(dominant[1]*100)}%)\n"
        f"💡 {report['suggestion']}\n\n"
        "⚠️ 以上为预览。教师可要求修改内容，确认后说「发送」推送给家长。"
    )

    return json.dumps({
        "preview": preview,
        "report_data": report,
        "student_id": student_id,
        "student_name": sname,
        "next_action": "教师确认后调 send_report_to_parent 发送",
    }, ensure_ascii=False)


# ── send_report_to_parent ──

async def send_report_to_parent(
    student_id: str = "",
    report_data: str = "",
) -> str:
    """发送家长报告 — 将确认后的报告推送给绑定家长

    何时用：教师确认报告预览后说"发送""发给家长""推送"
    会发生什么：查绑定的家长，写 ParentNotification(type='weekly_report')，
               家长端消息Tab可看到，点击展开完整报告
    返回：确认发送结果
    NOT for 预览 — 先用 generate_parent_report"""
    import httpx as _httpx

    if not student_id:
        return json.dumps({"error": "请提供 student_id"}, ensure_ascii=False)

    api_base = "http://127.0.0.1:8000"
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{api_base}/api/parent/send-report/{student_id}",
                json={"report": report_data} if report_data else {},
            )
        if resp.status_code != 200:
            return json.dumps({"error": f"发送失败: HTTP {resp.status_code}"}, ensure_ascii=False)
        data = resp.json()
        if data.get("success"):
            return json.dumps({
                "result": data.get("message", "报告已发送"),
                "parent_name": data.get("parent_name", ""),
                "student_name": data.get("student_name", ""),
            }, ensure_ascii=False)
        return json.dumps({"error": data.get("message", "发送失败")}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"发送失败: {str(e)}"}, ensure_ascii=False)


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

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_write())
        except RuntimeError:
            pass
    except Exception:
        pass


def _get_store_context():
    """Get SqliteStore from agent context."""
    try:
        from agent.langgraph_agent_v2 import get_store_context
        return get_store_context()
    except Exception:
        return None
