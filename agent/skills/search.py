"""真题搜索 Skill"""
from agent.skill_registry import registry


@registry.register(
    name="search_exam_bank",
    description="搜索历年高考化学真题。按知识点关键词、年份、难度筛选。返回匹配题目的内容、选项、答案和知识点标签。",
    parameters={
        "keyword": "搜索关键词，如 盐类水解、电离平衡、氧化还原",
        "year": "年份筛选（可选），如 2024",
        "difficulty": "难度筛选（可选），easy/medium/hard",
        "limit": "返回数量（可选），默认5",
    },
)
async def search_exam_bank(
    keyword: str = "",
    year: str = "",
    difficulty: str = "",
    limit: str = "5",
) -> dict:
    from app.services.exam_bank import exam_bank_service

    limit_int = int(limit)
    results = exam_bank_service.search_questions(
        knowledge_point=keyword or None,
        year=int(year) if year else None,
        difficulty=difficulty or None,
        limit=limit_int,
    )
    return {
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
    }
