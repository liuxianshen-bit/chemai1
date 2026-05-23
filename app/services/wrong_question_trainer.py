"""
错题强化训练服务
根据错题生成同知识点的变式练习题
"""

from datetime import datetime
from typing import List, Optional, Dict
from app.models.database import (
    Student, Question, StudentAnswer, ExamRecord,
    get_db, Difficulty
)
from app.services.llm_service import llm_service


class WrongQuestionTrainer:
    """错题强化训练服务"""

    def __init__(self):
        pass

    def get_student_wrong_questions(
        self,
        student_id: str,
        limit: int = 20,
        knowledge_point_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        获取学生的错题列表
        按错误次数和最近复习时间排序
        """
        db_gen = get_db()
        db = next(db_gen)

        try:
            # 查询学生的错题（未掌握的）
            query = db.query(StudentAnswer, Question).join(
                Question, StudentAnswer.question_id == Question.question_id
            ).filter(
                StudentAnswer.student_id == student_id,
                StudentAnswer.is_correct == False
            )

            # 按知识点筛选
            if knowledge_point_filter:
                query = query.filter(
                    Question.knowledge_points.contains(knowledge_point_filter)
                )

            results = query.all()

            # 统计每道错题的错误次数
            wrong_count_map = {}
            for answer, question in results:
                if question.question_id not in wrong_count_map:
                    wrong_count_map[question.question_id] = {
                        "question": question,
                        "count": 0,
                        "last_error_at": answer.answered_at
                    }
                wrong_count_map[question.question_id]["count"] += 1

            # 转换为列表并排序
            sorted_wrongs = sorted(
                wrong_count_map.values(),
                key=lambda x: (x["count"], x["last_error_at"]),
                reverse=True
            )

            return [
                {
                    "question_id": item["question"].question_id,
                    "content": item["question"].content,
                    "options": item["question"].options,
                    "answer": item["question"].answer,
                    "analysis": item["question"].analysis,
                    "knowledge_points": item["question"].knowledge_points,
                    "difficulty": item["question"].difficulty.value if item["question"].difficulty else "medium",
                    "wrong_count": item["count"],
                    "last_error_at": item["last_error_at"].isoformat() if item["last_error_at"] else None
                }
                for item in sorted_wrongs[:limit]
            ]
        finally:
            db.close()

    def generate_variant_questions(
        self,
        original_question_id: str,
        quantity: int = 3
    ) -> List[Dict]:
        """
        根据原题生成变式练习题
        使用LLM生成同知识点但不同表述的题目
        """
        db_gen = get_db()
        db = next(db_gen)

        try:
            # 获取原题信息
            original = db.query(Question).filter(
                Question.question_id == original_question_id
            ).first()

            if not original:
                return []

            # 调用LLM生成变式题
            knowledge_points = original.knowledge_points or []
            if isinstance(knowledge_points, str):
                try:
                    import json
                    knowledge_points = json.loads(knowledge_points)
                except:
                    knowledge_points = [knowledge_points]

            llm_result = llm_service.generate_variant_questions(
                original_content=original.content,
                original_answer=original.answer,
                knowledge_points=knowledge_points,
                difficulty=original.difficulty.value if original.difficulty else "medium",
                quantity=quantity
            )

            variants = []
            if llm_result.get("success") and "questions" in llm_result.get("content", ""):
                try:
                    import json
                    content = llm_result["content"]
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    data = json.loads(content)
                    variants = data.get("questions", [])
                except:
                    pass

            return variants
        finally:
            db.close()

    def create_training_session(
        self,
        student_id: str,
        question_ids: List[str]
    ) -> Dict:
        """
        创建强化训练会话
        返回训练会话ID和题目列表
        """
        db_gen = get_db()
        db = next(db_gen)

        try:
            session_id = f"train_{student_id}_{int(datetime.utcnow().timestamp())}"

            # 获取题目详情
            questions = db.query(Question).filter(
                Question.question_id.in_(question_ids)
            ).all()

            question_list = []
            for q in questions:
                question_list.append({
                    "question_id": q.question_id,
                    "content": q.content,
                    "options": q.options,
                    "answer": q.answer,
                    "analysis": q.analysis,
                    "knowledge_points": q.knowledge_points,
                    "difficulty": q.difficulty.value if q.difficulty else "medium"
                })

            return {
                "session_id": session_id,
                "student_id": student_id,
                "questions": question_list,
                "total_count": len(question_list)
            }
        finally:
            db.close()

    def submit_training_result(
        self,
        session_id: str,
        student_id: str,
        answers: List[Dict]
    ) -> Dict:
        """
        提交训练结果
        返回正确率和建议
        """
        db_gen = get_db()
        db = next(db_gen)

        try:
            correct_count = 0
            total_count = len(answers)

            results = []
            for ans in answers:
                question = db.query(Question).filter(
                    Question.question_id == ans.get("question_id")
                ).first()

                if question:
                    student_answer = str(ans.get("answer", "")).strip().upper()
                    correct_answer = str(question.answer or "").strip().upper()
                    is_correct = student_answer == correct_answer

                    if is_correct:
                        correct_count += 1

                    # 保存答题记录
                    answer_record = StudentAnswer(
                        answer_id=f"train_{session_id}_{question.question_id}",
                        student_id=student_id,
                        question_id=question.question_id,
                        student_answer=ans.get("answer"),
                        is_correct=is_correct,
                        answered_at=datetime.utcnow()
                    )
                    db.add(answer_record)

                    results.append({
                        "question_id": question.question_id,
                        "is_correct": is_correct,
                        "your_answer": ans.get("answer"),
                        "correct_answer": question.answer
                    })

            db.commit()

            accuracy = correct_count / total_count if total_count > 0 else 0

            # 生成建议
            suggestions = self._generate_suggestions(accuracy, results)

            return {
                "session_id": session_id,
                "correct_count": correct_count,
                "total_count": total_count,
                "accuracy": round(accuracy, 2),
                "results": results,
                "suggestions": suggestions
            }
        finally:
            db.close()

    def _generate_suggestions(self, accuracy: float, results: List[Dict]) -> str:
        """根据正确率生成学习建议"""
        if accuracy >= 0.9:
            return "太棒了！这类题目你已经掌握得很好了，可以尝试更高难度的挑战。"
        elif accuracy >= 0.7:
            return "做得不错！继续保持，多练习类似题目可以达到完美掌握。"
        elif accuracy >= 0.5:
            return "还需要继续努力。建议查看错题的解析，理解解题思路。"
        else:
            return "这部分知识还需要加强。建议先复习相关知识点，再重新练习。"


# 全局实例
wqt = WrongQuestionTrainer()


def get_student_wrong_questions(student_id: str, limit: int = 20) -> List[Dict]:
    return wqt.get_student_wrong_questions(student_id, limit)


def generate_variant_questions(original_question_id: str, quantity: int = 3) -> List[Dict]:
    return wqt.generate_variant_questions(original_question_id, quantity)


def create_training_session(student_id: str, question_ids: List[str]) -> Dict:
    return wqt.create_training_session(student_id, question_ids)


def submit_training_result(session_id: str, student_id: str, answers: List[Dict]) -> Dict:
    return wqt.submit_training_result(session_id, student_id, answers)
