"""
OCR服务封装
用于: F1 答题卡识别
支持: 智谱AI GLM-OCR (主要) / 腾讯OCR (备用)
"""
import base64
import json
import os
import subprocess
from typing import Dict, List, Optional, Tuple
from app.core.config import settings


class OCRService:
    """
    OCR服务 - 整合智谱GLM-OCR和腾讯OCR
    优先使用智谱OCR，失败则降级到Mock
    """

    def __init__(self):
        self.zhipu_key = settings.ZHIPU_API_KEY or os.getenv("ZHIPU_API_KEY", "")
        self.enabled = bool(self.zhipu_key)

    def recognize_handwriting(self, image_data: bytes) -> Dict:
        """手写文字识别"""
        if not self.enabled:
            return self._ocr_not_configured()
        return self._call_zhipu_ocr(image_data, "handwriting")

    def recognize_print(self, image_data: bytes) -> Dict:
        """印刷文字识别"""
        if not self.enabled:
            return self._ocr_not_configured()
        return self._call_zhipu_ocr(image_data, "print")

    def recognize_table(self, image_data: bytes) -> Dict:
        """表格识别"""
        if not self.enabled:
            return self._ocr_not_configured()
        return self._call_zhipu_ocr(image_data, "table")

    def recognize_answer_sheet(self, image_data: bytes) -> Dict:
        """
        答题卡识别（整合）
        识别学生作答结果，返回结构化数据
        """
        if not self.enabled:
            return self._ocr_not_configured()

        # 调用智谱OCR
        result = self._call_zhipu_ocr(image_data, "answer_sheet")

        # 检查调用是否成功（HTTP层面）
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "OCR服务调用失败"),
                "student_id": "unknown",
                "student_name": "待识别",
                "answers": {},
                "scores": {},
                "total_score": 0,
                "confidence": 0,
                "raw_text": "",
                "provider": "zhipu",
                "mock": False
            }

        # 解析智谱OCR结果，尝试提取答题卡信息
        parsed_result = self._parse_answer_sheet_from_zhipu(result)

        # 如果解析也失败，返回失败状态
        if not parsed_result.get("success"):
            return parsed_result

        return parsed_result

    def _call_zhipu_ocr(self, image_data: bytes, ocr_type: str = "general") -> Dict:
        """
        调用智谱GLM-OCR API
        端点: https://open.bigmodel.cn/api/paas/v4/files/ocr
        """
        try:
            import tempfile

            # 写入临时文件
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(image_data)
                tmp_path = tmp.name

            # 智谱GLM-OCR API调用 - 正确端点
            api_url = "https://open.bigmodel.cn/api/paas/v4/files/ocr"

            cmd = [
                "curl", "-s", "-k", "-X", "POST", api_url,
                "-H", f"Authorization: Bearer {self.zhipu_key}",
                "-F", f"file=@{tmp_path}",
                "-F", "tool_type=hand_write"
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=30)
            response_text = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""

            # 删除临时文件
            try:
                os.unlink(tmp_path)
            except:
                pass

            if result.returncode == 0 and response_text:
                data = json.loads(response_text)
                return {
                    "success": True,
                    "type": ocr_type,
                    "data": data,
                    "raw_text": self._extract_text_from_zhipu(data),
                    "confidence": 0.9,
                    "provider": "zhipu"
                }
            else:
                return {
                    "success": False,
                    "error": response_text or "OCR call failed",
                    "provider": "zhipu"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": "zhipu"
            }

    def _extract_text_from_zhipu(self, data: Dict) -> str:
        """从智谱OCR响应中提取文本"""
        try:
            if isinstance(data, dict):
                # 智谱OCR返回格式: {"words_result": [{"words": "文本"}, ...]}
                words_result = data.get("words_result", [])
                if words_result:
                    texts = [item.get("words", "") for item in words_result]
                    return " ".join(texts)
                # 尝试其他格式
                if "data" in data and isinstance(data["data"], dict):
                    return data["data"].get("text", "")
                return str(data)
            return str(data)
        except:
            return ""

    def _parse_answer_sheet_from_zhipu(self, ocr_result: Dict) -> Dict:
        """
        从智谱OCR结果中解析答题卡
        返回结构化的学生答题信息
        即使不是标准答题卡格式，也返回识别结果供预览
        """
        raw_text = ocr_result.get("raw_text", "") or ""

        # 检查OCR是否真正成功 - 检查原始数据中的status字段
        original_data = ocr_result.get("data", {})
        if isinstance(original_data, dict) and original_data.get("status") == "failed":
            # OCR识别失败，但仍然返回原始文本供预览
            return {
                "success": True,  # 改为返回success，让预览页显示
                "error": original_data.get("message", "OCR识别失败"),
                "student_id": "unknown",
                "student_name": "待识别",
                "answers": {},
                "scores": {},
                "total_score": 0,
                "confidence": 0,
                "raw_text": raw_text,
                "provider": "zhipu",
                "mock": False,
                "is_partial": True  # 标记为部分识别
            }

        # 检查是否有有效的识别文本
        if not raw_text or len(raw_text) < 10:
            return {
                "success": True,  # 改为返回success，让预览页显示
                "error": "未识别到有效文本，请手动输入",
                "student_id": "unknown",
                "student_name": "待识别",
                "answers": {},
                "scores": {},
                "total_score": 0,
                "confidence": 0,
                "raw_text": raw_text,
                "provider": "zhipu",
                "mock": False,
                "is_partial": True
            }

        # 尝试从识别的文本中提取学号和答案
        student_id = self._extract_student_id(raw_text)
        answers = self._extract_answers(raw_text)

        if student_id and answers:
            return {
                "success": True,
                "student_id": student_id,
                "student_name": "学生",
                "answers": answers,
                "scores": {k: 6 for k in answers.keys()},  # 默认每题6分
                "total_score": len(answers) * 6,
                "confidence": ocr_result.get("confidence", 0.85),
                "raw_text": raw_text,
                "provider": "zhipu",
                "mock": False,
                "is_partial": False
            }

        # 即使没有解析到学号和答案，也返回原始文本供预览
        # 让老师在预览页面手动输入或修正
        return {
            "success": True,  # 始终返回success
            "error": None,
            "student_id": student_id or "unknown",
            "student_name": "待识别",
            "answers": answers if answers else {},  # 返回可能提取到的答案
            "scores": {k: 6 for k in answers.keys()} if answers else {},
            "total_score": len(answers) * 6 if answers else 0,
            "confidence": ocr_result.get("confidence", 0.85),
            "raw_text": raw_text,
            "provider": "zhipu",
            "mock": False,
            "is_partial": True if not (student_id and answers) else False
        }

    def _extract_student_id(self, text: str) -> Optional[str]:
        """从文本中提取学号"""
        import re
        # 尝试匹配学号格式 (如: 202401001)
        match = re.search(r'[2][0][2][4][0-9]{5}', text)
        return match.group(0) if match else None

    def _extract_answers(self, text: str) -> Dict[str, str]:
        """从文本中提取答案选项 (简化版)"""
        import re
        answers = {}
        # 尝试匹配 "1. A" 或 "1.A" 格式
        matches = re.findall(r'([1-9]|10)[.、]?\s*([A-D])', text)
        for q_num, answer in matches:
            answers[q_num] = answer.upper()
        return answers

    def _ocr_not_configured(self) -> Dict:
        """OCR 服务未配置时的错误返回"""
        return {
            "success": False,
            "error": "OCR 服务未配置，请设置 ZHIPU_API_KEY 环境变量",
            "student_id": "",
            "student_name": "",
            "answers": {},
            "scores": {},
            "total_score": 0,
            "confidence": 0,
            "provider": "none",
        }


# 向后兼容
class TencentOCRService(OCRService):
    """向后兼容的腾讯OCR服务（实际使用智谱OCR）"""
    pass


class OCRParser:
    """
    OCR结果解析器
    将腾讯OCR返回的原始JSON转换为结构化数据
    """

    @staticmethod
    def parse_handwriting_result(ocr_result: Dict) -> List[Dict]:
        """
        解析手写识别结果
        返回: [{"text": "A", "bbox": [x1,y1,x2,y2]}, ...]
        """
        texts = ocr_result.get("TextDetections", [])
        results = []
        for item in texts:
            results.append({
                "text": item.get("DetectedText", ""),
                "confidence": item.get("Confidence", 0),
                "bbox": item.get("Polygon", [])
            })
        return results

    @staticmethod
    def parse_answer_sheet(ocr_result: Dict, question_count: int = 10) -> Dict:
        """
        解析答题卡识别结果
        提取: 学号、姓名、每道题作答

        参数:
            ocr_result: 腾讯OCR返回的原始JSON
            question_count: 题目数量
        """
        # 实际解析逻辑应该根据答题卡模板来
        # 这里返回简化版

        return {
            "student_id": ocr_result.get("student_id", ""),
            "student_name": ocr_result.get("student_name", ""),
            "answers": ocr_result.get("answers", {}),
            "scores": ocr_result.get("scores", {}),
            "total_score": ocr_result.get("total_score", 0),
            "confidence": ocr_result.get("confidence", 0)
        }

    @staticmethod
    def validate_answer_sheet(answers: Dict, question_count: int = 10) -> Tuple[bool, List[str]]:
        """
        验证答题卡数据完整性
        返回: (是否有效, 错误列表)
        """
        errors = []

        if not answers.get("student_id"):
            errors.append("缺少学号")

        if not answers.get("student_name"):
            errors.append("缺少姓名")

        # 检查题目数量
        for q_num in range(1, question_count + 1):
            q_key = str(q_num)
            if q_key not in answers.get("answers", {}):
                errors.append(f"缺少第{q_num}题答案")

        return len(errors) == 0, errors


# 全局OCR服务实例
ocr_service = TencentOCRService()
ocr_parser = OCRParser()
