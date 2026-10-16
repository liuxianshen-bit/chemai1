"""OCR Sheet Provider — MinerU (default) + Baidu OCR (production).

Usage:
    provider = get_ocr_provider()
    result = provider.extract(image_path)

Returns: {"student_id": "...", "student_name": "...", "answers": [...]}
"""
import os, json, re
from app.config import config


class BaseOCRProvider:
    def extract(self, image_path: str) -> dict:
        raise NotImplementedError


class MinerUProvider(BaseOCRProvider):
    """MinerU local OCR — development provider. Handwriting support is limited."""

    def extract(self, image_path: str) -> dict:
        try:
            from mineru.cli.client import MinerUClient
            client = MinerUClient()
            result = client.parse(image_path)
            text = result.get("content", "") if isinstance(result, dict) else str(result)

            student_id, student_name = self._extract_student(text)
            answers = self._extract_answers(text)

            return {
                "student_id": student_id,
                "student_name": student_name,
                "answers": answers,
                "raw_text": text[:2000],
            }
        except ImportError:
            return {"student_id": "", "student_name": "", "answers": [], "error": "MinerU not installed"}
        except Exception as e:
            return {"student_id": "", "student_name": "", "answers": [], "error": str(e)}

    def _extract_student(self, text: str) -> tuple:
        sid, name = "", ""
        id_match = re.search(r'学号[:\s]*(\d{6,10})', text)
        if id_match:
            sid = id_match.group(1)
        name_match = re.search(r'姓名[:\s]*([\u4e00-\u9fff]{2,4})', text)
        if name_match:
            name = name_match.group(1)
        # Fallback: scan for generic id pattern
        if not sid:
            id_generic = re.search(r'\b(\d{8,10})\b', text)
            if id_generic:
                sid = id_generic.group(1)
        return sid, name

    def _extract_answers(self, text: str) -> list:
        answers = []
        q_pattern = re.finditer(r'(\d{1,2})[\.\、\)]\s*([A-Da-d]+.*?)(?=\d{1,2}[\.\、\)]|$)', text)
        for m in q_pattern:
            q_num = int(m.group(1))
            ans_raw = m.group(2).strip()
            ans = ans_raw[0].upper() if ans_raw else "?"
            answers.append({"q_number": q_num, "type": "choice", "answer": ans, "confidence": 0.7})
        return answers


class BaiduOCRProvider(BaseOCRProvider):
    """Baidu OCR — production provider for handwriting recognition."""

    def extract(self, image_path: str) -> dict:
        from app.services.baidu_auth import get_token
        token = get_token()
        # ... (production implementation)
        return {"student_id": "", "student_name": "", "answers": [], "error": "Baidu OCR not yet implemented"}


_providers = {
    "mineru": MinerUProvider,
    "baidu": BaiduOCRProvider,
}


def get_ocr_provider() -> BaseOCRProvider:
    provider_cls = _providers.get(config.OCR_SHEET_PROVIDER, MinerUProvider)
    return provider_cls()
