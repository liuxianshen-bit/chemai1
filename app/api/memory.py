"""
学情记忆 API
用于将诊断结果持久化到学生的 memory.md 文件
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List

router = APIRouter()


class DiagnosisCompleteRequest(BaseModel):
    """诊断完成请求"""
    student_id: str
    barrier_type: Dict[str, float]  # {concept: 0.3, reading: 0.5, expression: 0.2}
    dominant_barrier: str  # 主要障碍类型
    weak_kps: List[str]  # 薄弱知识点列表


class DiagnosisCompleteResponse(BaseModel):
    """诊断完成响应"""
    success: bool
    message: str
    student_id: str


@router.post("/diagnosis-complete", response_model=DiagnosisCompleteResponse)
async def memory_diagnosis_complete(request: DiagnosisCompleteRequest):
    """
    将诊断结果持久化到学生的 memory.md 文件

    这是一个关键的后端API，用于实现"持久进化的Agent学习系统"：
    1. 老师上传答题卡 → OCR识别
    2. 老师确认学生身份
    3. 生成统计和诊断
    4. 【此处】将诊断结果写入学生的memory.md，实现学情持久化

    下次该学生再上传答题卡时，Agent会读取memory.md，
    结合历史诊断给出更准确的学情分析。
    """
    try:
        # 导入 memory handler
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        from chem_skills.chemistry_memory.handler import MemoryHandler

        handler = MemoryHandler()

        # 调用 memory_on_diagnosis_completed
        result = handler.memory_on_diagnosis_completed(
            student_id=request.student_id,
            barrier_type=request.barrier_type,
            dominant_barrier=request.dominant_barrier,
            weak_kps=request.weak_kps
        )

        if result.get("success"):
            return DiagnosisCompleteResponse(
                success=True,
                message="诊断结果已持久化到学生记忆",
                student_id=request.student_id
            )
        else:
            return DiagnosisCompleteResponse(
                success=False,
                message=f"持久化失败: {result.get('error', '未知错误')}",
                student_id=request.student_id
            )

    except Exception as e:
        return DiagnosisCompleteResponse(
            success=False,
            message=f"持久化异常: {str(e)}",
            student_id=request.student_id
        )


@router.get("/student/{student_id}")
async def get_student_memory(student_id: str):
    """
    获取学生的学情记忆
    """
    try:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        from chem_skills.chemistry_memory.handler import MemoryHandler

        handler = MemoryHandler()
        result = handler.memory_student_get(student_id, memory_type="all")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_memory_stats():
    """
    获取记忆系统统计信息
    """
    try:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        from chem_skills.chemistry_memory.handler import MemoryHandler

        handler = MemoryHandler()
        result = handler.memory_stats()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
