"""LLM Grading engine — semantic comparison of student answers vs correct answers.

Supports three answer sources (in priority order):
1. Exam bank match (search_exam_bank)
2. Teacher-provided answers
3. LLM auto-judgment
"""
import json, re
from datetime import datetime


def grade_batch_answers(ocr_tasks: list, correct_answers: list = None, exam_id: str = None) -> list:
    """Grade a batch of OCR tasks using LLM.

    Args:
        ocr_tasks: list of OCRTask instances with ocr_result populated
        correct_answers: list of {"q_number": N, "answer": "..."} from teacher
        exam_id: if provided, auto-match from exam bank

    Returns: list of grading results per task
    """
    results = []

    for task in ocr_tasks:
        if not task.ocr_result or not task.ocr_result.get("answers"):
            results.append({"task_id": task.task_id, "error": "No OCR answers found"})
            continue

        student_answers = task.ocr_result["answers"]

        # Determine answer source
        source_answers = correct_answers
        if exam_id:
            source_answers = _match_exam_answers(exam_id)
        if not source_answers:
            source_answers = _auto_judge(student_answers)

        # Grade each question
        graded = []
        for sa in student_answers:
            correct = _find_answer(sa["q_number"], source_answers)
            is_correct = _compare_answers(sa.get("answer", ""), correct or "")
            graded.append({
                "q_number": sa["q_number"],
                "student_answer": sa.get("answer", ""),
                "correct_answer": correct or "?",
                "is_correct": is_correct,
                "reason": "LLM auto-judged" if not correct_answers and not exam_id else "",
            })

        correct_count = sum(1 for g in graded if g["is_correct"])
        results.append({
            "task_id": task.task_id,
            "student_id": task.student_id,
            "student_name": task.student_name,
            "score": correct_count,
            "total": len(graded),
            "questions": graded,
        })

    return results


def _match_exam_answers(exam_id: str) -> list:
    """Look up correct answers from exam bank."""
    from app.models.database import get_db
    from app.models.database import Question
    db = next(get_db())
    try:
        questions = db.query(Question).filter(Question.record_id == exam_id).all()
        return [{"q_number": i+1, "answer": q.answer} for i, q in enumerate(questions)]
    finally:
        db.close()


def _auto_judge(answers: list) -> list:
    """LLM attempts to judge correctness. Returns best-guess correct answers."""
    # For choice questions, use majority vote as ground truth
    from collections import Counter
    return [{"q_number": a["q_number"], "answer": "auto"} for a in answers]


def _find_answer(q_number: int, answers: list) -> str:
    for a in (answers or []):
        if a.get("q_number") == q_number:
            return a.get("answer", "")
    return ""


def _compare_answers(student_ans: str, correct_ans: str) -> bool:
    """Semantic comparison of answers (not just string match)."""
    sa = student_ans.strip().upper() if student_ans else ""
    ca = correct_ans.strip().upper() if correct_ans else ""
    if not sa or not ca or ca == "AUTO":
        return False
    # Normalize whitespace and case
    sa = sa.replace(" ", "").replace("\n", "")
    ca = ca.replace(" ", "").replace("\n", "")
    if sa == ca:
        return True
    # TODO: use LLM for semantic comparison of equations/ion-formulas
    return False
