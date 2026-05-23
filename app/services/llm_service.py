"""
通义千问(LLM)服务
用于: AI出题/题目审核/障碍诊断/历年真题关联
"""
import os
import json
import base64
from typing import List, Dict, Optional
from app.core.config import settings


class LLMService:
    """
    LLM服务封装
    支持: 通义千问 / ChatGLM(备选)

    使用方式:
    1. 通义千问: 设置 DASHSCOPE_API_KEY 环境变量
    2. ChatGLM: 设置 CHATGLM_API_URL 环境变量
    """

    def __init__(self):
        self.dashscope_key = settings.DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = settings.LLM_MODEL
        self.enabled = bool(self.dashscope_key)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict:
        """
        通用文本生成 (使用curl调用DashScope API)
        """
        if not self.enabled:
            return self._mock_generate(prompt)

        try:
            import subprocess
            import shlex

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # DashScope API 调用 - 使用 compatible-mode 端点
            api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            # 使用curl调用API (-k 禁用SSL验证)
            cmd = [
                "curl", "-s", "-k", "-X", "POST", api_url,
                "-H", f"Authorization: Bearer {self.dashscope_key}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload)
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=60)
            response_text = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""

            if result.returncode == 0:
                response_data = json.loads(response_text)
                # 解析 chat/completions 响应格式
                choices = response_data.get("choices", [{}])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                return {
                    "success": True,
                    "content": content,
                    "usage": response_data.get("usage", {}),
                    "request_id": response_data.get("id", "")
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or "curl failed",
                    "code": result.returncode
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _mock_generate(self, prompt: str) -> Dict:
        """模拟生成（无API Key时使用）"""
        return {
            "success": True,
            "content": "[MOCK] 这是模拟的LLM响应。配置 DASHSCOPE_API_KEY 后将返回真实内容。",
            "usage": {"input_tokens": len(prompt), "output_tokens": 50},
            "request_id": "mock_request_id"
        }

    def generate_questions(
        self,
        knowledge_points: List[str],
        difficulty: str,
        quantity: int = 10,
        rag_context: List[Dict] = None
    ) -> Dict:
        """
        AI生成化学题目
        基于知识点/难度/数量生成练习题
        如果提供了RAG上下文（相似真题），则基于这些真题生成变种题
        """
        system_prompt = """你是一位资深高中化学教师,擅长根据知识点生成高质量的化学练习题。

要求:
1. 题目科学性100%正确,化学方程式必须配平
2. 题目语言清晰,无歧义
3. 选项设置要有区分度
4. 注明题目考查的知识点
5. 适当设置陷阱选项考察学生易错点

返回格式（JSON）:
{
    "questions": [
        {
            "content": "题目正文",
            "options": ["A. 选项", "B. 选项", "C. 选项", "D. 选项"],
            "answer": "正确答案字母",
            "knowledge_points": ["知识点1", "知识点2"],
            "difficulty": "easy/medium/hard",
            "trap_hints": ["陷阱提示"]
        }
    ]
}"""

        # 构建prompt：如果有RAG上下文（相似真题），基于这些真题生成变种题
        if rag_context and len(rag_context) >= 3:
            # 有足够的相似真题，使用RAG模式
            context_str = "\n\n".join([
                f"【真题{i+1}】{q.get('content', q.get('question', ''))} "
                f"答案: {q.get('answer', '')} "
                f"知识点: {', '.join(q.get('knowledge_points', []))}"
                for i, q in enumerate(rag_context[:5])
            ])
            prompt = f"""基于以下历年真题生成变种题，保持相同的知识点和难度风格，但题目内容要有变化:

【参考真题】
{context_str}

请生成{quantity}道{difficulty}难度的化学变种题，直接返回JSON:
"""
        else:
            # 没有RAG上下文，纯LLM生成
            prompt = f"""请为以下知识点生成{quantity}道{difficulty}难度的化学练习题:

知识点: {', '.join(knowledge_points)}

请直接返回JSON,不要有其他文字:"""

        return self.generate_text(prompt, system_prompt, temperature=0.7)

    def generate_variant_questions(
        self,
        original_content: str,
        original_answer: str,
        knowledge_points: List[str],
        difficulty: str = "medium",
        quantity: int = 3
    ) -> Dict:
        """
        生成变式练习题
        基于原题生成同知识点但不同表述的题目
        """
        system_prompt = """你是一位资深高中化学教师,擅长生成变式练习题。

要求:
1. 保持相同的知识点和难度
2. 题目内容要有变化（换数据、换问法、换情境）
3. 选项要重新设计，避免与原题相同
4. 保持陷阱设置的风格
5. 化学方程式必须配平正确

返回格式（JSON）:
{
    "questions": [
        {
            "content": "变式题正文",
            "options": ["A. 选项", "B. 选项", "C. 选项", "D. 选项"],
            "answer": "正确答案字母",
            "knowledge_points": ["知识点1", "知识点2"],
            "difficulty": "easy/medium/hard"
        }
    ]
}"""

        prompt = f"""请为以下原题生成{quantity}道变式练习题:

【原题】
{original_content}
答案: {original_answer}
知识点: {', '.join(knowledge_points)}
难度: {difficulty}

请生成内容不同但考查相同知识点的变式题，直接返回JSON:"""

        return self.generate_text(prompt, system_prompt, temperature=0.8)

    def audit_question_with_llm(self, question_content: str) -> Dict:
        """
        使用LLM进行题目安全审核
        作为规则引擎的二次校验
        """
        system_prompt = """你是一位高中化学教研专家,负责审核AI生成的化学题目是否合格。

审核维度:
1. 科学性: 题目内容/化学方程式/概念是否正确
2. 准确性: 知识点对应是否准确
3. 适当性: 难度是否适中,是否符合高中生水平
4. 陷阱设置: 陷阱选项是否合理

请严格审核,发现任何科学性错误必须指出。"""

        prompt = f"""请审核以下高中化学题目:

{question_content}

请返回JSON:
{{
  "is_qualified": true/false,
  "issues": ["问题1", "问题2"],
  "suggestions": ["修改建议1", ...]
}}"""

        return self.generate_text(prompt, system_prompt, temperature=0.3)

    def diagnose_barrier_type(
        self,
        student_error_history: List[Dict],
        question_content: str,
        student_answer: str,
        correct_answer: str
    ) -> Dict:
        """
        诊断学生障碍类型
        - 概念理解型(concept): 学生对化学概念的理解存在偏差
        - 审题障碍型(reading): 学生读取题目信息不全/审题错误
        - 表述障碍型(expression): 学生理解正确答案但无法规范表述
        """
        system_prompt = """你是一位教育心理学专家,擅长分析学生的学习障碍类型。

障碍类型定义:
1. 概念理解型(concept): 学生对化学概念的理解存在偏差,导致解题错误
2. 审题障碍型(reading): 学生读取题目信息不全,或对题目条件的理解有误
3. 表述障碍型(expression): 学生理解正确答案,但无法规范表述

请根据学生的答题情况判断其障碍类型。"""

        prompt = f"""学生答题情况分析:

题目: {question_content}
学生答案: {student_answer}
正确答案: {correct_answer}

学生历史错误(供参考): {json.dumps(student_error_history, ensure_ascii=False)}

请返回JSON:
{{
  "barrier_type": "concept/reading/expression",
  "confidence": 0.0-1.0,
  "reasoning": "判断理由",
  "suggestion": "教学干预建议"
}}"""

        return self.generate_text(prompt, system_prompt, temperature=0.3)

    def check_answer_consistency(
        self,
        question_content: str,
        correct_answer: str,
        ocr_answer: str
    ) -> Dict:
        """
        检查OCR识别答案与标准答案的一致性
        用于OCR预览阶段的LLM辅助分析

        返回:
        {
            "is_consistent": bool,  # OCR答案与标准答案是否一致
            "llm_answer": str,  # LLM认为的答案
            "confidence": float,  # LLM判断置信度
            "suggestion": str  # 建议
        }
        """
        system_prompt = """你是一位高中化学老师,擅长从学生答案中判断其答题情况。

请仔细分析以下信息，判断OCR识别的学生答案是否正确。

注意:
- OCR可能存在识别误差，特别是手写字体
- 如果学生答案与标准答案不一致，需要判断是学生真的答错了，还是OCR识别错误
- 考虑化学选择题的常见干扰项设置"""

        prompt = f"""题目内容: {question_content}
标准答案: {correct_answer}
OCR识别的学生答案: {ocr_answer}

请仔细分析:
1. OCR识别的答案格式是否清晰可辨
2. 学生实际想表达的是否是正确答案
3. 如果是化学方程式或复杂表达式，OCR识别是否可能有误差

返回JSON:
{{
  "is_consistent": true/false,  // OCR答案是否与标准答案一致
  "llm_answer": "LLM认为学生实际想要的答案",  // 可能是识别错误
  "confidence": 0.0-1.0,  // 判断置信度
  "suggestion": "如果不一致，说明原因和修改建议"
}}"""

        return self.generate_text(prompt, system_prompt, temperature=0.3)

    def find_similar_historical_questions(
        self,
        question_content: str,
        knowledge_point: str,
        limit: int = 5
    ) -> Dict:
        """
        查找历年同类真题
        用于F6历年真题关联
        """
        system_prompt = """你是一位高考化学命题专家,负责分析题目的相似性和命题风格。

请分析给定题目与历年高考题的相似度,帮助判断AI出题与真实考试的贴近程度。"""

        prompt = f"""分析以下题目的特征,并与历年高考化学题进行关联:

目标题目: {question_content}
知识点: {knowledge_point}

请返回JSON:
{{
  "question_features": ["特征1", "特征2"],
  "similar_questions": [
    {{
      "source": "2024年全国卷T15",
      "year": 2024,
      "region": "全国卷",
      "similarity": 0.85,
      "common_features": ["都考查了...", "都设置了..."]
    }}
  ]
}}"""

        return self.generate_text(prompt, system_prompt, temperature=0.5)

    def generate_learning_plan(
        self,
        student_name: str,
        barrier_type: str,
        weak_knowledge_points: List[str],
        recent_performance: Optional[Dict] = None
    ) -> Dict:
        """
        生成个性化学习计划
        基于学生障碍类型和薄弱知识点生成定制化学习路径
        """
        system_prompt = """你是一位资深高中化学教师,擅长根据学生的学习情况制定个性化学习计划。

学习计划要求:
1. 针对学生的具体障碍类型制定干预策略
2. 结合薄弱知识点安排循序渐进的学习内容
3. 计划要具体可执行,包括每日/每周任务
4. 包含激励性话语,增强学生学习信心
5. 计划周期建议2-4周

返回格式（JSON）:
{
    "plan_title": "学生学习计划标题",
    "plan_period": "2周/4周",
    "daily_tasks": [
        {
            "day": "第1-3天",
            "content": "具体学习任务",
            "duration": "约30分钟",
            "resource_type": "视频/练习/复习"
        }
    ],
    "weekly_goals": [
        {
            "week": "第一周",
            "goals": ["掌握xx知识点", "完成xx练习"],
            "milestone": "达成后可进入下一阶段"
        }
    ],
    "barrier针对性的干预": [
        {
            "barrier": "概念理解型",
            "strategy": "使用思维导图理解概念内涵",
            "practise_tips": "通过对比练习区分易混淆概念"
        }
    ],
    "motivation_tips": ["鼓励话语1", "鼓励话语2"],
    "parent_communication_suggestion": "给家长的建议"
}"""

        barrier_desc = {
            "concept": "概念理解型 - 学生对化学概念的理解存在偏差",
            "reading": "审题障碍型 - 学生读取题目信息不全/审题错误",
            "expression": "表述障碍型 - 学生理解正确答案但无法规范表述"
        }.get(barrier_type, barrier_type)

        performance_str = ""
        if recent_performance:
            performance_str = f"""
学生近期表现:
- 最近正确率: {recent_performance.get('recent_accuracy', '暂无数据')}%
- 最近练习日期: {recent_performance.get('recent_practice_date', '暂无数据')}
- 进步情况: {recent_performance.get('improvement', '暂无数据')}"""

        prompt = f"""请为学生 {student_name} 生成个性化学习计划:

学生障碍类型: {barrier_desc}
薄弱知识点: {', '.join(weak_knowledge_points) if weak_knowledge_points else '暂无记录'}
{performance_str}

请直接返回JSON,不要有其他文字:"""

        return self.generate_text(prompt, system_prompt, temperature=0.7)

    def analyze_paper_with_vision(
        self,
        image_data: str,  # base64编码的图片
        paper_type: str = "mixed"  # answer_sheet/printed/handwritten/mixed
    ) -> Dict:
        """
        使用智谱多模态大模型(GLM-4.6V)分析试卷图片
        当OCR识别结果被老师否定后调用此方法

        参数:
            image_data: base64编码的试卷图片
            paper_type: 试卷类型
                - answer_sheet: 答题卡
                - printed: 印刷试卷
                - handwritten: 手写试卷
                - mixed: 混合（印刷题目+手写作答）

        返回:
            {
                "success": bool,
                "student_id": str,
                "student_name": str,
                "questions": [{number, content, options, student_answer, correct_answer}],
                "raw_text": str,  # 原始识别文本
                "message": str
            }
        """
        # 检查是否有智谱API Key
        zhipu_key = os.getenv("ZHIPU_API_KEY", "") or settings.ZHIPU_API_KEY
        if not zhipu_key:
            return {
                "success": False,
                "error": "未配置智谱API Key",
                "message": "请配置 ZHIPU_API_KEY 环境变量"
            }

        try:
            import subprocess

            # 智谱GLM-4V多模态API端点
            api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

            # 根据试卷类型构建分析prompt
            prompts = {
                "answer_sheet": """请分析这张答题卡图片，识别出：
1. 学生学号和姓名（如果可见）
2. 每道题的作答答案（A/B/C/D）
3. 返回JSON格式结果

返回格式：
{
  "student_id": "学号",
  "student_name": "姓名",
  "questions": [
    {"number": "1", "student_answer": "A"},
    {"number": "2", "student_answer": "B"}
  ],
  "message": "识别说明"
}""",

                "printed": """请分析这张印刷试卷图片，识别出：
1. 试卷标题
2. 所有题目内容和选项
3. 标准答案（如果可见）
4. 返回JSON格式结果

返回格式：
{
  "title": "试卷标题",
  "questions": [
    {"number": "1", "content": "题目内容", "options": ["A. 选项", "B. 选项"], "correct_answer": "A"},
    {"number": "2", "content": "题目内容", "options": ["A. 选项", "B. 选项"], "correct_answer": "B"}
  ],
  "message": "识别说明"
}""",

                "handwritten": """请分析这张手写试卷图片，识别出：
1. 学生姓名（如果可见）
2. 所有手写题目内容
3. 手写作答内容
4. 返回JSON格式结果

返回格式：
{
  "student_name": "姓名",
  "questions": [
    {"number": "1", "content": "手写题目内容", "student_answer": "手写作答"},
    {"number": "2", "content": "手写题目内容", "student_answer": "手写作答"}
  ],
  "message": "识别说明"
}""",

                "mixed": """请分析这张混合试卷图片（印刷题目+手写作答），识别出：
1. 学生学号和姓名（如果可见）
2. 所有印刷题目内容和选项
3. 学生的手写作答内容
4. 返回JSON格式结果

返回格式：
{
  "student_id": "学号",
  "student_name": "姓名",
  "questions": [
    {"number": "1", "content": "印刷题目内容", "options": ["A. 选项", "B. 选项"], "student_answer": "A"},
    {"number": "2", "content": "印刷题目内容", "options": ["A. 选项", "B. 选项"], "student_answer": "手写内容"}
  ],
  "message": "识别说明"
}"""
            }

            prompt = prompts.get(paper_type, prompts["mixed"])

            # 根据图片数据自动判断MIME类型
            # PNG: 89 50 4E 47 ... (base64: iVBORw0K)
            # JPEG: FF D8 FF ... (base64: /9j/4)
            mime_type = "image/png"
            if image_data.startswith('/9j/') or image_data.startswith('iVBOR'):
                # 检查原始字节来判断
                try:
                    raw_bytes = base64.b64decode(image_data[:24] if len(image_data) >= 24 else image_data)
                    if raw_bytes[:4] == b'\x89PNG':
                        mime_type = "image/png"
                    elif raw_bytes[:3] == b'\xff\xd8\xff':
                        mime_type = "image/jpeg"
                except:
                    pass

            # 构建messages - 使用智谱GLM-4V格式
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"}
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]

            # 智谱GLM-4V API payload
            payload = {
                "model": "glm-4v",
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 2000
            }

            # 使用curl调用智谱API
            cmd = [
                "curl", "-s", "-k", "-X", "POST", api_url,
                "-H", f"Authorization: Bearer {zhipu_key}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload)
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)
            response_text = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""

            if result.returncode == 0 and response_text:
                response_data = json.loads(response_text)

                # 检查是否有错误
                if response_data.get("error"):
                    error_info = response_data.get("error", {})
                    error_code = error_info.get("code", "unknown")
                    error_msg = error_info.get("message", "API错误")
                    return {
                        "success": False,
                        "error": f"{error_code}: {error_msg}",
                        "message": "多模态分析失败，请检查API配置"
                    }

                # 智谱返回格式: choices[0].message.content
                choices = response_data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                else:
                    content = ""

                # 尝试解析返回的JSON
                try:
                    # 提取JSON（可能在markdown代码块中）
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]

                    result_data = json.loads(content.strip())

                    return {
                        "success": True,
                        "student_id": result_data.get("student_id", ""),
                        "student_name": result_data.get("student_name", ""),
                        "questions": result_data.get("questions", []),
                        "raw_text": content,
                        "message": result_data.get("message", "识别完成")
                    }
                except json.JSONDecodeError:
                    # JSON解析失败，返回原始文本
                    return {
                        "success": True,
                        "student_id": "",
                        "student_name": "",
                        "questions": [],
                        "raw_text": content,
                        "message": "识别完成，请查看原始文本"
                    }
            else:
                return {
                    "success": False,
                    "error": response_text or "Vision API调用失败",
                    "message": "多模态分析失败，请检查API配置"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "多模态分析异常"
            }

    def _mock_vision_result(self) -> Dict:
        """模拟多模态分析结果（无API Key时使用）"""
        return {
            "success": True,
            "student_id": "202401001",
            "student_name": "张三",
            "questions": [
                {"number": "1", "content": "题目1", "options": ["A", "B", "C", "D"], "student_answer": "A"},
                {"number": "2", "content": "题目2", "options": ["A", "B", "C", "D"], "student_answer": "B"},
                {"number": "3", "content": "题目3", "options": ["A", "B", "C", "D"], "student_answer": "C"},
            ],
            "raw_text": "[MOCK] 这是模拟的多模态分析结果。配置 DASHSCOPE_API_KEY 后将返回真实内容。",
            "message": "Mock模式：模拟识别完成"
        }


class ChatGLMService:
    """
    智谱ChatGLM服务（备选）
    用于对数据隐私要求极高的场景
    支持本地部署
    """

    def __init__(self):
        self.api_url = os.getenv("CHATGLM_API_URL", "http://localhost:8001")
        self.enabled = False

    def generate_text(self, prompt: str, **kwargs) -> Dict:
        """调用ChatGLM API"""
        if not self.enabled:
            return {"success": False, "error": "ChatGLM not enabled"}

        try:
            import httpx
            response = httpx.post(
                self.api_url,
                json={"prompt": prompt, **kwargs},
                timeout=30.0
            )
            if response.status_code == 200:
                return {"success": True, "content": response.json().get("response", "")}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# 全局LLM服务实例
llm_service = LLMService()
chatglm_service = ChatGLMService()
