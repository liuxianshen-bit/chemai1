"""
测试脚本：验证 Skill Handler 能正确调用 ChemAI API
"""
import asyncio
import sys
from pathlib import Path

# 添加 hermes-skills 目录到 Python 路径
HERMES_SKILLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HERMES_SKILLS_DIR))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'chemai-backend'))

# 现在可以导入了
from chemistry_diagnosis.handler import DiagnosisHandler


async def test_diagnosis():
    """测试障碍诊断 Handler"""
    handler = DiagnosisHandler()

    print("=" * 60)
    print("测试 1: 获取老师诊断配置")
    print("=" * 60)
    result = await handler.diagnosis_config_get("test_teacher")
    print(f"结果: {result}")
    print()

    print("=" * 60)
    print("测试 2: 获取学生障碍详情 (需要数据库数据)")
    print("=" * 60)
    try:
        result = await handler.diagnosis_barrier_student("test_student_001")
        print(f"结果: {result}")
    except Exception as e:
        print(f"预期错误 (无数据): {e}")
    print()


async def test_exam():
    """测试出题 Handler"""
    # 延迟导入避免路径问题
    from chemistry_exam.handler import ExamHandler

    handler = ExamHandler()

    print("=" * 60)
    print("测试 3: 获取真题集列表")
    print("=" * 60)
    try:
        result = await handler.exam_get_exam_sets()
        print(f"真题集数量: {result.get('total', 0)}")
    except Exception as e:
        print(f"错误: {e}")
    print()

    print("=" * 60)
    print("测试 4: 化学方程式配平检查")
    print("=" * 60)
    try:
        result = await handler.exam_balance_check("2H2 + O2 → 2H2O")
        print(f"配平检查结果: {result}")
    except Exception as e:
        print(f"错误: {e}")
    print()


def main():
    print("\n" + "=" * 60)
    print("Chem Skills 集成测试")
    print("=" * 60 + "\n")

    asyncio.run(test_diagnosis())
    asyncio.run(test_exam())

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
