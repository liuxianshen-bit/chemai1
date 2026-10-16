"""Test LLM grading: answer comparison, source resolution, result generation."""
import pytest


class TestAnswerComparison:
    def test_exact_match(self):
        from app.services.llm_grading import _compare_answers
        assert _compare_answers("B", "B") == True
        assert _compare_answers("A", "B") == False

    def test_case_insensitive(self):
        from app.services.llm_grading import _compare_answers
        assert _compare_answers("b", "B") == True
        assert _compare_answers("c", "C") == True

    def test_whitespace_normalized(self):
        from app.services.llm_grading import _compare_answers
        assert _compare_answers(" B ", "B") == True

    def test_empty_handling(self):
        from app.services.llm_grading import _compare_answers
        assert _compare_answers("", "B") == False
        assert _compare_answers("A", "") == False


class TestGradingPipeline:
    def test_grade_batch_with_answers(self, db_session):
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from datetime import datetime
        task = OCRTask(
            task_id="ocr_grade_test", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            student_id="202610101", student_name="test",
            ocr_result={"answers": [
                {"q_number": 1, "answer": "B"}, {"q_number": 2, "answer": "A"}
            ]},
            created_at=datetime.utcnow(),
        )
        db_session.add(task)
        db_session.commit()

        correct = [{"q_number": 1, "answer": "B"}, {"q_number": 2, "answer": "C"}]
        results = grade_batch_answers([task], correct_answers=correct)
        assert len(results) == 1
        assert results[0]["student_name"] == "test"
        assert results[0]["score"] == 1  # Q1 correct, Q2 wrong
        assert results[0]["questions"][0]["is_correct"] == True
        assert results[0]["questions"][1]["is_correct"] == False

    def test_grade_empty_ocr(self):
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from datetime import datetime
        task = OCRTask(
            task_id="ocr_empty", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            ocr_result=None,
            created_at=datetime.utcnow(),
        )
        results = grade_batch_answers([task], correct_answers=[])
        assert results[0].get("error") is not None
