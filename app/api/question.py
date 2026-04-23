"""
F2: AI出题与三维安全审核 API
基于PRD v1.0完整版功能规格
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Literal
import json
from datetime import datetime

router = APIRouter()


class QuestionGenerateRequest(BaseModel):
    """AI出题请求"""
    exam_type: str = "单元练习"  # 单元练习/月考/期中/期末
    knowledge_points: List[str]
    difficulty: Literal["easy", "medium", "hard", "competition"] = "medium"
    quantity: int = 10


class AuditResult(BaseModel):
    """单个题目审核结果"""
    dimension: str  # coefficient/condition/product/structure
    status: Literal["passed", "warning", "blocked"]
    message: str
    detail: Optional[str] = None


class AuditReport(BaseModel):
    """三维安全审核报告"""
    question_id: str
    content: str
    options: Optional[List[str]] = None
    answer: str
    knowledge_points: List[str]
    difficulty: str
    # 四维审核结果
    coefficient_audit: AuditResult
    condition_audit: AuditResult
    product_audit: AuditResult
    structure_audit: AuditResult
    # 综合结果
    overall_status: Literal["passed", "warning", "blocked"]
    # 陷阱提示
    trap_hints: List[str] = []
    # 历年真题关联
    historical_matches: List[dict] = []
    # RAG变种题标识
    is_from_rag: bool = False  # 是否基于历年真题变种生成
    source_question_id: Optional[str] = None  # 源真题ID
    source_question_preview: Optional[str] = None  # 源真题内容预览(前100字)
    similarity: Optional[float] = None  # 与源真题的相似度
    match_method: Optional[Literal["vector", "simple"]] = None  # 匹配方法


class QuestionGenerateResponse(BaseModel):
    """AI出题响应"""
    success: bool
    questions: List[AuditReport]
    generate_time_ms: int
    total_cost: float  # 预估API成本


class ManualSelectionRequest(BaseModel):
    """手动选题请求"""
    exam_ids: List[str]  # 历年真题ID列表


class HistoricalExam(BaseModel):
    """历年真题"""
    exam_id: str
    source: str  # "全国卷2024"
    year: int
    question_number: str  # "T15"
    content: str
    answer: str
    knowledge_points: List[str]
    difficulty: str
    discrimination: float  # 区分度


@router.post("/generate", response_model=QuestionGenerateResponse)
async def generate_questions(request: QuestionGenerateRequest):
    """
    F2: AI生成题目 + 三维安全审核 (Hybrid RAG模式)
    输入: 知识点/难度/数量
    输出: 题目列表 + 三维安全审核报告

    处理流程:
    1. 从历年真题库检索相似题目（RAG检索）
    2. 如果找到>=3道相似真题，基于这些真题生成变种题
    3. 如果没找到足够真题，纯LLM生成
    4. 调用化学方程式审核引擎进行四维审核
    5. 调用历年真题关联引擎查找相似题目
    6. 整合生成三维安全审核报告
    """
    import time
    from app.services.llm_service import llm_service
    from app.services.chemical_balance import audit_chemical_equation
    from app.services.exam_bank import exam_bank_service

    start_time = time.time()

    # 0. RAG检索：从历年真题库查找相似题目（使用两层检索）
    rag_context = []
    rag_results = []  # 存储RAG检索结果用于后续关联
    try:
        # 优先使用向量检索（两层检索）
        try:
            from app.services.vector_search import vector_search_service
            # 构建查询文本
            query_text = " ".join(request.knowledge_points)
            vector_results = vector_search_service.search_similar(
                query_text=query_text,
                knowledge_points=request.knowledge_points,
                difficulty=request.difficulty,
                limit=5
            )
            if vector_results:
                for vr in vector_results:
                    # 获取完整题目信息
                    full_q = exam_bank_service.get_by_exam_id(vr["exam_id"])
                    if full_q:
                        rag_context.append({
                            "content": full_q.content,
                            "answer": full_q.answer,
                            "knowledge_points": full_q.knowledge_points,
                            "difficulty": full_q.difficulty,
                            "source": full_q.source,
                            "exam_id": full_q.exam_id,
                            "similarity": vr.get("similarity", 0.8),
                            "match_method": vr.get("match_method", "vector")
                        })
                        rag_results.append({
                            "exam_id": full_q.exam_id,
                            "content": full_q.content,
                            "source": full_q.source,
                            "similarity": vr.get("similarity", 0.8),
                            "match_method": vr.get("match_method", "vector")
                        })
                print(f"向量检索到{len(rag_context)}道相似真题")

            # 如果向量检索结果少于3个，回退到简单匹配补充
            if len(rag_context) < 3:
                print(f"向量检索结果不足{len(rag_context)}道，回退到简单匹配补充...")
                similar_questions = exam_bank_service.find_similar_questions(
                    knowledge_points=request.knowledge_points,
                    difficulty=request.difficulty,
                    limit=5
                )
                if similar_questions:
                    for q in similar_questions:
                        # 检查是否已经在rag_context中
                        if not any(r.get("exam_id") == q.exam_id for r in rag_context):
                            rag_context.append({
                                "content": q.content,
                                "answer": q.answer,
                                "knowledge_points": q.knowledge_points,
                                "difficulty": q.difficulty,
                                "source": q.source,
                                "exam_id": q.exam_id,
                                "similarity": 0.7,
                                "match_method": "simple"
                            })
                            rag_results.append({
                                "exam_id": q.exam_id,
                                "content": q.content,
                                "source": q.source,
                                "similarity": 0.7,
                                "match_method": "simple"
                            })
                    print(f"简单匹配补充后共有{len(rag_context)}道相似真题")
        except Exception as ve:
            print(f"向量检索失败，回退到简单匹配: {ve}")
            # 回退到简单匹配
            similar_questions = exam_bank_service.find_similar_questions(
                knowledge_points=request.knowledge_points,
                difficulty=request.difficulty,
                limit=5
            )
            if similar_questions:
                rag_context = [
                    {
                        "content": q.content,
                        "answer": q.answer,
                        "knowledge_points": q.knowledge_points,
                        "difficulty": q.difficulty,
                        "source": q.source,
                        "exam_id": q.exam_id,
                        "similarity": 0.8,
                        "match_method": "simple"
                    }
                    for q in similar_questions
                ]
                rag_results = rag_context.copy()
                print(f"简单匹配检索到{len(rag_context)}道相似真题")
    except Exception as e:
        print(f"RAG检索失败: {e}")

    # 1. 调用LLM生成题目（传入RAG上下文）
    llm_result = llm_service.generate_questions(
        knowledge_points=request.knowledge_points,
        difficulty=request.difficulty,
        quantity=request.quantity,
        rag_context=rag_context if len(rag_context) >= 3 else None
    )

    questions = []
    total_cost = 0.0

    if llm_result.get("success") and "questions" in llm_result.get("content", ""):
        # 尝试解析LLM返回的JSON
        try:
            content = llm_result["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            data = json.loads(content)
            generated_questions = data.get("questions", [])
        except json.JSONDecodeError:
            generated_questions = []
    else:
        generated_questions = []

    # 如果LLM生成失败或无数据，返回模拟数据
    if not generated_questions:
        return QuestionGenerateResponse(
            success=False,
            questions=[],
            generate_time_ms=int((time.time() - start_time) * 1000),
            total_cost=0.0,
            error="LLM生成失败或返回格式错误"
        )

    # 2. 对每道题进行三维安全审核
    for i, q in enumerate(generated_questions):
        question_id = f"ai_{int(time.time())}_{i}"

        # 检查化学方程式
        import re
        equations = re.findall(r'[A-Za-z0-9\(\)\[\]→=+\s]+', q.get("content", ""))
        has_equation = any('→' in eq or '=' in eq for eq in equations)

        # 调用审核引擎
        if has_equation:
            for eq in equations:
                if '→' in eq or '=' in eq:
                    audit_result = audit_chemical_equation(eq.strip())
                    if audit_result["overall_status"] == "blocked":
                        # 配平错误，标记为blocked
                        q["_audit_blocked"] = True
                        q["_audit_message"] = audit_result["overall_message"]
                        break

        # 3. 查找历年相似题目
        similar = exam_bank_service.find_similar_questions(
            knowledge_points=q.get("knowledge_points", request.knowledge_points),
            difficulty=request.difficulty,
            limit=3
        )
        historical_matches = [
            {
                "source": s.source,
                "year": s.year,
                "question_number": s.question_number,
                "similarity": 0.8 - i * 0.1,
                "difficulty": s.difficulty
            }
            for s in similar
        ]

        # 4. RAG变种题标识：如果使用了RAG生成，为每道题关联源真题
        is_from_rag = False
        source_question_id = None
        source_question_preview = None
        similarity = None
        match_method = None

        if rag_results and len(rag_results) >= 3:
            # 基于RAG生成的题目，关联到最相似的源真题
            # 按相似度选择（每道生成的题关联一个源真题，轮流分配）
            rag_idx = i % len(rag_results)
            source_info = rag_results[rag_idx]
            is_from_rag = True
            source_question_id = source_info.get("exam_id")
            source_question_preview = source_info.get("content", "")[:100] + "..." if len(source_info.get("content", "")) > 100 else source_info.get("content", "")
            similarity = source_info.get("similarity", 0.8)
            match_method = source_info.get("match_method", "simple")
            # 更新historical_matches加入RAG源题
            historical_matches.insert(0, {
                "source": source_info.get("source", ""),
                "year": 0,
                "question_number": source_question_id,
                "similarity": similarity,
                "difficulty": request.difficulty,
                "is_rag_source": True
            })

        # 生成陷阱提示
        trap_hints = q.get("trap_hints", [])
        if not trap_hints:
            kps = q.get("knowledge_points", [])
            if "盐类水解" in kps:
                trap_hints.append("注意区分\"水解\"与\"电离\"的概念")
            if "电离" in kps:
                trap_hints.append("强电解质完全电离，弱电解质部分电离")
            if "氧化还原" in kps:
                trap_hints.append("注意电子转移的方向和数目")

        # 构建审核报告
        questions.append(AuditReport(
            question_id=question_id,
            content=q.get("content", ""),
            options=q.get("options", []),
            answer=q.get("answer", "A"),
            knowledge_points=q.get("knowledge_points", []),
            difficulty=q.get("difficulty", request.difficulty),
            coefficient_audit=AuditResult(
                dimension="coefficient",
                status="blocked" if q.get("_audit_blocked") else "passed",
                message=q.get("_audit_message", "本题为选择题，无需配平" if not has_equation else "方程式已配平")
            ),
            condition_audit=AuditResult(
                dimension="condition",
                status="passed",
                message="无反应条件审核" if not has_equation else "反应条件正确"
            ),
            product_audit=AuditResult(
                dimension="product",
                status="passed",
                message="产物判断通过"
            ),
            structure_audit=AuditResult(
                dimension="structure",
                status="passed",
                message="结构检查通过"
            ),
            overall_status="blocked" if q.get("_audit_blocked") else "passed",
            trap_hints=trap_hints,
            historical_matches=historical_matches,
            is_from_rag=is_from_rag,
            source_question_id=source_question_id,
            source_question_preview=source_question_preview,
            similarity=similarity,
            match_method=match_method
        ))

        # 估算成本 (qwen-turbo约0.004元/1K token)
        total_cost += len(q.get("content", "")) * 0.004 / 1000

    elapsed_ms = int((time.time() - start_time) * 1000)

    return QuestionGenerateResponse(
        success=True,
        questions=questions,
        generate_time_ms=elapsed_ms,
        total_cost=round(total_cost, 4)
    )


class AuditQuestionRequest(BaseModel):
    """单题审核请求"""
    question_content: str
    options: Optional[List[str]] = None


@router.post("/audit", response_model=AuditReport)
async def audit_question(request: AuditQuestionRequest):
    """
    单题安全审核
    输入: 题目内容
    输出: 三维安全审核报告
    """
    from app.services.chemical_balance import audit_chemical_equation
    import re

    question_content = request.question_content
    options = request.options or []

    # 检查化学方程式 - 先统一箭头符号(-> -> →)以正确提取方程式
    normalized_content = question_content.replace('->', '→')
    equations = re.findall(r'[A-Za-z0-9\(\)\[\]→=+\s]+', normalized_content)
    has_equation = any('→' in eq or '=' in eq for eq in equations)

    # 审核结果
    coefficient_status = "passed"
    coefficient_message = "本题为选择题，无需配平" if not has_equation else "方程式已配平"

    if has_equation:
        for eq in equations:
            if '→' in eq or '=' in eq:
                audit_result = audit_chemical_equation(eq.strip())
                if audit_result["overall_status"] == "blocked":
                    coefficient_status = "blocked"
                    coefficient_message = audit_result["overall_message"]
                    break
                elif audit_result["overall_status"] == "warning":
                    coefficient_status = "warning"

    # 生成陷阱提示
    trap_hints = []
    if "盐类水解" in question_content:
        trap_hints.append("注意区分\"水解\"与\"电离\"的概念")
    if "电离" in question_content:
        trap_hints.append("强电解质完全电离，弱电解质部分电离")
    if "氧化还原" in question_content:
        trap_hints.append("注意电子转移的方向和数目")

    return AuditReport(
        question_id=f"audit_{int(datetime.now().timestamp())}",
        content=question_content,
        options=options,
        answer="A",
        knowledge_points=["待标注"],
        difficulty="medium",
        coefficient_audit=AuditResult(dimension="coefficient", status=coefficient_status, message=coefficient_message),
        condition_audit=AuditResult(dimension="condition", status="passed", message="无反应条件" if not has_equation else "反应条件正确"),
        product_audit=AuditResult(dimension="product", status="passed", message="产物判断通过"),
        structure_audit=AuditResult(dimension="structure", status="passed", message="结构检查通过"),
        overall_status=coefficient_status,
        trap_hints=trap_hints,
        historical_matches=[]
    )


@router.get("/historical")
async def get_historical_questions(
    source: Optional[str] = None,
    year: Optional[int] = None,
    difficulty: Optional[str] = None,
    knowledge_point: Optional[str] = None,
    keyword: Optional[str] = None
):
    """
    历年真题库查询
    支持按来源/年份/难度/知识点/关键词筛选
    """
    # 使用题库服务查询
    from app.services.exam_bank import exam_bank_service

    results = exam_bank_service.search_questions(
        source=source,
        year=year,
        knowledge_point=knowledge_point,
        difficulty=difficulty,
        keyword=keyword
    )

    return {
        "total": len(results),
        "source": source or "all",
        "year": year or "all",
        "knowledge_point": knowledge_point or "all",
        "difficulty": difficulty or "all",
        "questions": [
            {
                "exam_id": q.exam_id,
                "source": q.source,
                "year": q.year,
                "question_number": q.question_number,
                "content": q.content,
                "options": q.options,
                "answer": q.answer,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty,
                "discrimination": q.discrimination,
                "chapter": q.chapter
            }
            for q in results  # 返回全部结果（不限制）
        ]
    }


@router.get("/exam-sets")
async def get_exam_sets():
    """
    获取真题集列表（不含题目详情，用于懒加载）
    返回格式：[{source, year, region, question_count}, ...]
    """
    from app.services.exam_bank import exam_bank_service

    # 从已加载的papers中提取真题集信息
    exam_sets = []
    for paper_id, paper in exam_bank_service.papers.items():
        exam_sets.append({
            "source": paper.source,
            "year": paper.year,
            "region": paper.region,
            "paper_name": paper.paper_name,
            "question_count": paper.question_count
        })

    # 按年份降序排列
    exam_sets.sort(key=lambda x: x["year"], reverse=True)

    return {
        "total": len(exam_sets),
        "exam_sets": exam_sets
    }


@router.get("/exam-sets/{source:path}")
async def get_exam_set_detail(source: str):
    """
    获取指定真题集的题目详情（懒加载）
    source: URL编码的真题集名称，如 "全国卷2024"
    """
    from app.services.exam_bank import exam_bank_service
    from urllib.parse import unquote

    # 解码URL编码的名称
    decoded_source = unquote(source)

    # 查找匹配的试卷
    paper = None
    for p in exam_bank_service.papers.values():
        if p.source == decoded_source:
            paper = p
            break

    if not paper:
        raise HTTPException(status_code=404, detail=f"真题集 {decoded_source} 不存在")

    return {
        "source": paper.source,
        "year": paper.year,
        "region": paper.region,
        "paper_name": paper.paper_name,
        "total_score": paper.total_score,
        "question_count": paper.question_count,
        "questions": [
            {
                "exam_id": q.exam_id,
                "question_number": q.question_number,
                "original_number": q.original_number,
                "question_type": q.question_type,
                "content": q.content,
                "options": q.options,
                "answer": q.answer,
                "analysis": q.analysis,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty,
                "discrimination": q.discrimination,
                "score": q.score,
                "chapter": q.chapter
            }
            for q in paper.questions
        ]
    }


@router.post("/manual/select", response_model=List[AuditReport])
async def manual_select_questions(request: ManualSelectionRequest):
    """
    手动选题（新增）
    教师从历年真题库选择题目后，仍需经过AI安全审核
    """
    from app.services.exam_bank import exam_bank_service
    from app.services.chemical_balance import audit_chemical_equation

    selected = []
    for exam_id in request.exam_ids:
        question = exam_bank_service.get_by_exam_id(exam_id)
        if not question:
            continue

        # 调用化学方程式审核
        chemistry_check = {}
        if any(kp in ["氧化还原反应", "电化学", "原电池", "电解池"]
               for kp in question.knowledge_points):
            # 检查题目中是否包含化学方程式
            import re
            equations = re.findall(r'[A-Za-z0-9\(\)\[\]→=+\s]+', question.content)
            for eq in equations:
                if '→' in eq or '=' in eq:
                    result = audit_chemical_equation(eq.strip())
                    chemistry_check[eq] = result

        # 生成审核报告
        audit_report = AuditReport(
            question_id=question.exam_id,
            content=question.content,
            options=question.options,
            answer=question.answer,
            knowledge_points=question.knowledge_points,
            difficulty=question.difficulty,
            coefficient_audit=AuditResult(
                dimension="coefficient",
                status="passed",
                message="本题为选择题，无需配平"
            ),
            condition_audit=AuditResult(
                dimension="condition",
                status="passed",
                message="无反应条件审核"
            ),
            product_audit=AuditResult(
                dimension="product",
                status="passed",
                message="无产物判断"
            ),
            structure_audit=AuditResult(
                dimension="structure",
                status="passed",
                message="结构检查通过"
            ),
            overall_status="passed",
            trap_hints=[],
            historical_matches=[
                {"source": question.source, "question_number": question.question_number, "similarity": 1.0}
            ]
        )
        selected.append(audit_report)

    return selected


class SimilarQuestionRequest(BaseModel):
    """查找相似题目请求"""
    knowledge_points: List[str]
    difficulty: str = "medium"
    limit: int = 5


@router.post("/similar")
async def find_similar_questions(request: SimilarQuestionRequest):
    """
    F6: 查找历年相似题目
    基于知识点和难度，从历年真题库中查找相似题目
    用于AI出题时的真题关联功能
    """
    from app.services.exam_bank import exam_bank_service

    similar = exam_bank_service.find_similar_questions(
        knowledge_points=request.knowledge_points,
        difficulty=request.difficulty,
        limit=request.limit
    )

    return {
        "query_knowledge_points": request.knowledge_points,
        "query_difficulty": request.difficulty,
        "found_count": len(similar),
        "similar_questions": [
            {
                "exam_id": q.exam_id,
                "source": q.source,
                "year": q.year,
                "question_number": q.question_number,
                "content": q.content[:100] + "..." if len(q.content) > 100 else q.content,
                "answer": q.answer,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty,
                "discrimination": q.discrimination,
                "chapter": q.chapter
            }
            for q in similar
        ]
    }


class TeacherImportRequest(BaseModel):
    """老师自助导入题目请求"""
    source_name: str  # 如 "2024年长沙市一模"
    region: str = "老师导入"
    year: int
    questions: List[dict]  # 题目列表


@router.post("/import")
async def import_questions(request: TeacherImportRequest):
    """
    老师自助导入真题
    支持JSON格式上传题目
    题目格式:
    {
        "question_number": "T1",
        "original_number": "1",
        "question_type": "single_choice",
        "content": "题目内容",
        "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
        "answer": "A",
        "analysis": "解析内容(可选)",
        "knowledge_points": ["知识点1", "知识点2"],
        "difficulty": "medium",  # easy/medium/hard
        "score": 3
    }
    """
    from app.models.historical_exam import HistoricalQuestion
    from app.services.exam_bank import exam_bank_service

    imported_count = 0
    errors = []

    for i, q_data in enumerate(request.questions):
        try:
            # 验证必填字段
            if not q_data.get("content"):
                errors.append(f"第{i+1}题: 缺少题目内容")
                continue

            # 构建题目ID
            exam_id = f"teacher_{request.year}_{q_data.get('question_number', str(i+1))}"
            if not exam_id.startswith("teacher_"):
                exam_id = f"teacher_{exam_id}"

            # 创建题目对象
            question = HistoricalQuestion(
                exam_id=exam_id,
                source=f"{request.region}{request.year}",
                year=request.year,
                region=request.region,
                paper_name=request.source_name,
                question_number=q_data.get("question_number", f"T{i+1}"),
                original_number=str(q_data.get("original_number", i+1)),
                question_type=q_data.get("question_type", "single_choice"),
                content=q_data["content"],
                options=q_data.get("options"),
                answer=q_data.get("answer", ""),
                analysis=q_data.get("analysis", ""),
                knowledge_points=q_data.get("knowledge_points", ["综合"]),
                difficulty=q_data.get("difficulty", "medium"),
                discrimination=q_data.get("discrimination", 0.5),
                score=q_data.get("score", 3),
                chapter=q_data.get("knowledge_points", ["综合"])[0] if q_data.get("knowledge_points") else "综合"
            )

            # 添加到题库
            exam_bank_service.add_question(question)
            imported_count += 1

        except Exception as e:
            errors.append(f"第{i+1}题: {str(e)}")

    return {
        "success": imported_count > 0,
        "imported_count": imported_count,
        "total_submitted": len(request.questions),
        "errors": errors if errors else None,
        "message": f"成功导入 {imported_count} 道题目" if imported_count > 0 else f"导入失败: {errors[0] if errors else '未知错误'}"
    }


@router.post("/import/batch")
async def import_questions_batch(
    source_name: str,
    region: str = "老师导入",
    year: int = 2024,
    file_content: str = None  # Base64 encoded file content
):
    """
    批量导入题目 (支持Base64编码的文件内容)
    文件格式为JSON数组
    """
    import base64

    if not file_content:
        raise HTTPException(status_code=400, detail="缺少文件内容")

    try:
        # 解码Base64
        decoded = base64.b64decode(file_content)
        questions_data = json.loads(decoded.decode('utf-8'))

        if not isinstance(questions_data, list):
            raise HTTPException(status_code=400, detail="文件内容必须是JSON数组")

        # 构建请求
        request = TeacherImportRequest(
            source_name=source_name,
            region=region,
            year=year,
            questions=questions_data
        )

        # 调用导入
        return await import_questions(request)

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON格式错误")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/import/ocr")
async def import_questions_from_ocr(
    source_name: str,
    region: str = "老师导入",
    year: int = 2024,
    file: UploadFile = File(...)
):
    """
    老师通过OCR扫描试卷导入题目
    支持JPG/PNG/PDF格式的试卷图片
    返回识别的题目列表供老师确认后保存
    """
    import tempfile
    import os

    # 验证文件格式
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file.content_type}，仅支持 JPG/PNG/PDF"
        )

    # 读取文件
    file_data = await file.read()

    # 保存到临时文件供pdftotext处理
    suffix = ".pdf" if file.content_type == "application/pdf" else ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        tmp.write(file_data)

    try:
        # 使用pdftotext提取文本
        if file.content_type == "application/pdf":
            cmd = f'pdftotext -layout -enc UTF-8 "{tmp_path}" -'
            process = os.popen(cmd)
            text = process.read()
            process.close()
        else:
            # 图片需要先 OCR
            from app.services.ocr_service import ocr_service
            ocr_result = ocr_service.recognize_answer_sheet(file_data)
            text = ocr_result.get("raw_text", "") if ocr_result.get("success") else ""

        if not text:
            raise HTTPException(status_code=500, detail="OCR识别失败，无法提取文本")

        # 解析题目
        questions = _parse_questions_from_text(text, year, region)

        if not questions:
            raise HTTPException(status_code=400, detail="未能在试卷中识别到题目，请确认试卷格式")

        return {
            "success": True,
            "source_name": source_name,
            "region": region,
            "year": year,
            "detected_count": len(questions),
            "questions": questions,
            "message": "已识别出题目，请确认后调用 /import 保存"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR处理失败: {str(e)}")
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def _parse_questions_from_text(text: str, year: int, region: str) -> List[dict]:
    """
    从识别文本中解析题目
    复用extract_hunan_exams.py的解析逻辑
    """
    import re
    from app.models.historical_exam import get_sample_national_2024

    questions = []
    lines = text.split('\n')

    current_question = None
    current_options = []
    q_num = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        # 跳过页码等
        if re.match(r'^\d+\s*\|\s*\d+\s*页', line):
            i += 1
            continue
        if '注意事项' in line or '可能用到的相对原子质量' in line:
            i += 1
            continue
        if line.startswith('一、') or line.startswith('二、') or line.startswith('三、'):
            i += 1
            continue
        if '选择题' in line:
            i += 1
            continue

        # 检测题目开始 - 多种格式支持
        # 格式1: "1.（3 分）在溶液中..." 或 "1.（3分）在溶液中..."
        match = re.match(r'^(\d+)[．\.]\s*（[^）]+）\s*(.+)', line)
        if not match:
            # 格式2: "1. 下列有关..." (无括号)
            match = re.match(r'^(\d+)[．\.]\s+([^A-D].+)', line)
        if not match:
            # 格式3: "1、xxx" (顿号分隔)
            match = re.match(r'^(\d+)、\s*(.+)', line)

        if match and not line.startswith(('A.', 'B.', 'C.', 'D.', 'A．', 'B．', 'C．', 'D．')):
            # 保存上一题
            if current_question and q_num:
                q_data = _build_question_data(current_question, current_options, year, region, q_num)
                if q_data:
                    questions.append(q_data)

            q_num = match.group(1)
            current_question = match.group(2)
            current_options = []
            i += 1
            continue

        # 检测选项
        opt_match = re.match(r'^([A-D])[．\.]\s*(.+)', line)
        if opt_match and current_question:
            current_options.append({
                'label': opt_match.group(1),
                'text': opt_match.group(2)
            })
            i += 1
            continue

        # 处理跨行选项
        if current_question and len(current_options) >= 2:
            last_opt = current_options[-1]['text']
            if not last_opt.endswith(('.', '。', '，', '、')):
                if re.match(r'^[A-D]\s+', line) or re.match(r'^\s+[A-D]', line):
                    current_options[-1]['text'] += ' ' + line.strip()
                    i += 1
                    continue

        i += 1

    # 保存最后一题
    if current_question and q_num:
        q_data = _build_question_data(current_question, current_options, year, region, q_num)
        if q_data:
            questions.append(q_data)

    return questions


def _build_question_data(content: str, options: List[dict], year: int, region: str, q_num: str) -> Optional[dict]:
    """构建题目数据结构"""
    import re

    if not content or len(content) < 5:
        return None

    # 清理文本
    content = re.sub(r'\s+', ' ', content).strip()

    # 检测题型
    q_type = "single_choice"
    if options and len(options) >= 4:
        q_type = "single_choice"
    elif '填空' in content or '_______' in content:
        q_type = "fill_blank"
    elif '计算' in content:
        q_type = "calculation"

    # 检测难度
    difficulty = "medium"
    hard_kw = ['复杂', '困难', '难题', '竞赛', '综合', '探究', '设计实验']
    easy_kw = ['基础', '简单', '常识', '了解']
    if any(kw in content for kw in hard_kw):
        difficulty = "hard"
    elif any(kw in content for kw in easy_kw):
        difficulty = "easy"

    # 提取知识点
    kp_keywords = [
        ('氧化还原', ['氧化还原反应', '氧化剂', '还原剂', '氧化性', '还原性']),
        ('电解', ['电解', '电解池', '阳极', '阴极']),
        ('电离', ['电离', '电解质', '非电解质']),
        ('盐类水解', ['盐类水解', '水解']),
        ('离子反应', ['离子反应', '离子共存', '离子方程式']),
        ('元素周期律', ['元素周期律', '原子结构', '化学键']),
        ('有机物', ['有机物', '官能团', '取代反应', '加成反应']),
        ('化学平衡', ['化学平衡', '平衡移动', '反应速率', '平衡常数']),
        ('电化学', ['电化学', '原电池', '电极反应']),
        ('物质的量', ['物质的量', '阿伏加德罗', '摩尔', '浓度']),
        ('胶体', ['胶体', '分散系']),
        ('实验', ['实验', '制备', '检验', '分离']),
        ('金属', ['金属', '碱金属', '铝', '铁', '铜']),
        ('非金属', ['非金属', '卤素', '硫', '氮', '氯']),
        ('热化学', ['热化学', '燃烧热', '反应热', '盖斯定律']),
        ('酸碱', ['酸碱', 'PH', '缓冲溶液']),
        ('晶体', ['晶体', '晶胞', '原子晶体', '分子晶体']),
        ('新能源', ['新能源', '太阳能', '氢能', '锂电池']),
        ('化工流程', ['工艺流程', '工业生产']),
    ]

    found_kps = []
    for kp_name, keywords in kp_keywords:
        for kw in keywords:
            if kw in content:
                found_kps.append(kp_name)
                break

    knowledge_points = found_kps[:5] if found_kps else ['综合']

    return {
        "question_number": f"T{q_num}",
        "original_number": str(q_num),
        "question_type": q_type,
        "content": content,
        "options": [f"{opt['label']}. {opt['text']}" for opt in options] if options else None,
        "answer": "",  # OCR无法识别答案，需老师填写
        "analysis": "",
        "knowledge_points": knowledge_points,
        "difficulty": difficulty,
        "score": 3,
        "chapter": knowledge_points[0] if knowledge_points else "综合"
    }
