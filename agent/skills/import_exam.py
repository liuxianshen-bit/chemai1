"""试卷导入 Skill — MinerU PDF 解析 + 化学审核 + 入库"""
from agent.skill_registry import registry


@registry.register(
    name="import_exam_paper",
    description="上传试卷PDF，自动提取化学题目并审核入库。支持全国卷和各省市试卷。返回提取数量、审核结果和入库状态。",
    parameters={
        "pdf_path": "PDF文件路径（服务器上的路径）",
        "source": "试卷来源，如 湖南卷2025、全国卷2024",
        "year": "年份，如 2025",
        "auto_approve": "是否自动入库（true/false），默认false需人工审核",
    },
)
async def import_exam_paper(
    pdf_path: str = "",
    source: str = "未知来源",
    year: str = "2025",
    auto_approve: str = "false",
) -> dict:
    import os

    if not pdf_path or not os.path.exists(pdf_path):
        return {"error": f"PDF文件不存在: {pdf_path}"}

    auto = auto_approve.lower() == "true"

    # 1. 尝试调 MinerU（如果可用）
    mineru_available = False
    try:
        from app.services.mineru_service import MinerUClient

        client = MinerUClient()
        raw_questions = await client.extract_questions(pdf_path)
        mineru_available = True
    except (ImportError, Exception):
        # MinerU 不可用，回退到本地解析
        raw_questions = _fallback_extract(pdf_path)

    # 2. 化学审核
    from app.services.chemical_balance import audit_chemical_equation

    reviewed = []
    passed = 0
    for q in raw_questions:
        audit = None
        # 检查是否有方程式需要审核
        content = q.get("content", "") + q.get("question", "")
        if any(kw in content for kw in ["→", "=", "反应", "方程式"]):
            import re

            eq_match = re.search(r"([\d\w\(\)\+\s→=->]+)", content)
            if eq_match:
                audit = audit_chemical_equation(eq_match.group(1))

        reviewed.append(
            {
                **q,
                "audit_status": audit["overall_status"] if audit else "no_equation",
                "audit_detail": audit if audit else None,
            }
        )
        if audit is None or audit["overall_status"] == "passed":
            passed += 1

    # 3. 入库
    saved = 0
    if auto:
        try:
            from app.services.exam_bank import exam_bank_service

            saved = exam_bank_service.batch_import(reviewed, source, int(year))
        except Exception as e:
            return {
                "extracted": len(raw_questions),
                "passed_audit": passed,
                "saved": 0,
                "error": f"入库失败: {str(e)}",
                "mineru_used": mineru_available,
            }

    return {
        "extracted": len(raw_questions),
        "passed_audit": passed,
        "saved": saved,
        "auto_approved": auto,
        "needs_review": len(reviewed) - passed,
        "questions": reviewed if not auto else None,
        "mineru_used": mineru_available,
    }


def _fallback_extract(pdf_path: str) -> list[dict]:
    """无 MinerU 时的回退：提示需要手动安装"""
    return [
        {
            "number": "N/A",
            "content": f"PDF解析需要 MinerU 服务。请安装 Docker 并启动 MinerU 容器。文件: {pdf_path}",
            "options": [],
            "answer": "",
        }
    ]
