"""
历年真题库管理服务
负责: 加载/查询/标注历年真题
"""
import json
import os
from typing import List, Dict, Optional, Tuple
from app.core.config import settings
from app.models.historical_exam import HistoricalQuestion, ExamPaper


class ExamBankService:
    """
    历年真题库服务
    基于PRD: 覆盖全国卷2022-2024 + 湖南卷2022-2024
    """

    def __init__(self):
        self.questions: List[HistoricalQuestion] = []
        self.papers: Dict[str, ExamPaper] = {}
        self._load_exam_bank()

    def _load_exam_bank(self):
        """从文件加载真题数据"""
        exam_dir = settings.EXAM_QUESTIONS_PATH

        # 加载所有可用年份 (2008-2025)
        for year in [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014, 2013, 2012, 2011, 2010, 2009, 2008]:
            # 全国卷 - 优先full版本
            full_path = os.path.join(exam_dir, f"national_{year}_full.json")
            normal_path = os.path.join(exam_dir, f"national_{year}.json")
            if os.path.exists(full_path):
                self._load_from_file(full_path, "全国卷", year)
            elif os.path.exists(normal_path):
                self._load_from_file(normal_path, "全国卷", year)

            # 湖南卷 - 优先full版本
            full_path = os.path.join(exam_dir, f"hunan_{year}_full.json")
            normal_path = os.path.join(exam_dir, f"hunan_{year}.json")
            if os.path.exists(full_path):
                self._load_from_file(full_path, "湖南卷", year)
            elif os.path.exists(normal_path):
                self._load_from_file(normal_path, "湖南卷", year)

        # 如果没有数据,加载样例
        if not self.questions:
            self._load_sample_data()

    def _load_from_file(self, file_path: str, region: str, year: int):
        """从JSON文件加载"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            questions = [HistoricalQuestion(**q) for q in data.get("questions", [])]
            self.questions.extend(questions)

            # 构建试卷索引
            paper_id = f"{region}{year}"
            self.papers[paper_id] = ExamPaper(
                paper_id=paper_id,
                source=f"{region}{year}",
                year=year,
                region=region,
                paper_name=data.get("paper_name", ""),
                subject="化学",
                total_score=data.get("total_score", 100),
                question_count=len(questions),
                questions=questions
            )

    def _load_sample_data(self):
        """加载样例数据(开发测试用)"""
        from app.models.historical_exam import get_sample_national_2024, get_sample_hunan_2024

        nat_2024 = get_sample_national_2024()
        hun_2024 = get_sample_hunan_2024()

        self.questions.extend(nat_2024)
        self.questions.extend(hun_2024)

        # 构建试卷索引
        self.papers["全国卷2024"] = ExamPaper(
            paper_id="national_2024",
            source="全国卷2024",
            year=2024,
            region="全国卷",
            paper_name="2024年普通高等学校招生全国统一考试化学",
            subject="化学",
            total_score=100,
            question_count=len(nat_2024),
            questions=nat_2024
        )

        self.papers["湖南卷2024"] = ExamPaper(
            paper_id="hunan_2024",
            source="湖南卷2024",
            year=2024,
            region="湖南卷",
            paper_name="2024年湖南省普通高中学业水平选择性考试化学",
            subject="化学",
            total_score=100,
            question_count=len(hun_2024),
            questions=hun_2024
        )

    def search_questions(
        self,
        source: Optional[str] = None,
        year: Optional[int] = None,
        knowledge_point: Optional[str] = None,
        difficulty: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[HistoricalQuestion]:
        """
        查询真题
        支持按来源/年份/知识点/难度/关键词筛选
        """
        results = self.questions

        if source:
            results = [q for q in results if source in q.source]

        if year:
            results = [q for q in results if q.year == year]

        if knowledge_point:
            results = [q for q in results
                      if knowledge_point in q.knowledge_points]

        if difficulty:
            results = [q for q in results if q.difficulty == difficulty]

        if keyword:
            keyword_lower = keyword.lower()
            results = [q for q in results
                      if keyword_lower in q.content.lower()
                      or keyword_lower in q.answer.lower()]

        return results

    def get_by_exam_id(self, exam_id: str) -> Optional[HistoricalQuestion]:
        """根据ID获取题目"""
        for q in self.questions:
            if q.exam_id == exam_id:
                return q
        return None

    def find_similar_questions(
        self,
        knowledge_points: List[str],
        difficulty: str,
        limit: int = 5
    ) -> List[HistoricalQuestion]:
        """查找相似题目(用于F6历年真题关联)"""
        # 按知识点匹配
        matched = []
        for q in self.questions:
            # 计算知识点匹配度
            overlap = len(set(q.knowledge_points) & set(knowledge_points))
            if overlap > 0:
                matched.append((q, overlap))

        # 按匹配度排序
        matched.sort(key=lambda x: x[1], reverse=True)

        # 过滤难度
        result = [q for q, _ in matched if q.difficulty == difficulty][:limit]

        # 如果难度匹配不足,补充其他难度
        if len(result) < limit:
            others = [q for q, _ in matched if q not in result][:limit - len(result)]
            result.extend(others)

        return result

    def get_exam_paper(self, source: str, year: int) -> Optional[ExamPaper]:
        """获取完整试卷"""
        key = f"{source}{year}"
        return self.papers.get(key)

    def get_knowledge_point_stats(self) -> Dict[str, Dict]:
        """统计各知识点出现的频次和难度分布"""
        stats = {}
        for q in self.questions:
            for kp in q.knowledge_points:
                if kp not in stats:
                    stats[kp] = {"count": 0, "difficulties": [], "sources": []}
                stats[kp]["count"] += 1
                stats[kp]["difficulties"].append(q.difficulty)
                stats[kp]["sources"].append(q.source)

        # 计算各难度占比
        for kp, data in stats.items():
            diff_count = {}
            for d in data["difficulties"]:
                diff_count[d] = diff_count.get(d, 0) + 1
            data["difficulty_distribution"] = {
                k: v / len(data["difficulties"]) for k, v in diff_count.items()
            }

        return stats

    def add_question(self, question: HistoricalQuestion):
        """添加新题目，如果已存在则更新"""
        # 检查是否已存在
        for i, q in enumerate(self.questions):
            if q.exam_id == question.exam_id:
                self.questions[i] = question
                return
        self.questions.append(question)

    def export_to_file(self, source: str, year: int, output_dir: str):
        """导出试卷到JSON文件"""
        paper = self.get_exam_paper(source, year)
        if not paper:
            return False

        output_path = os.path.join(output_dir, f"{source}_{year}.json")
        os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(paper.model_dump(), f, ensure_ascii=False, indent=2)

        return True


# 全局真题库服务实例
exam_bank_service = ExamBankService()
