"""真题搜索 Skill — PydanticAI 版本（PoC）
对比原始 search.py，验证 @agent.tool 迁移模式
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    """搜索结果"""
    total: int
    questions: list[dict]


def search_exam_bank_plain(
    keyword: str = "",
    year: Optional[int] = None,
    difficulty: Optional[str] = None,
    limit: int = 5,
) -> SearchResult:
    """搜索历年高考化学真题，返回匹配题目的内容、选项、答案和知识点标签。

    Args:
        keyword: 搜索关键词，如 盐类水解、电离平衡、氧化还原
        year: 年份筛选（可选），如 2024
        difficulty: 难度筛选（可选），easy/medium/hard
        limit: 返回数量（可选），默认5
    """
    from app.services.exam_bank import exam_bank_service

    results = exam_bank_service.search_questions(
        knowledge_point=keyword or None,
        year=year,
        difficulty=difficulty or None,
        limit=limit,
    )
    return SearchResult(
        total=len(results),
        questions=[
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
    )
