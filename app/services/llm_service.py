"""
ChemAI LLM Service — MiMo-V2.5 (主力) / DashScope / DeepSeek
"""
import os, json, base64, time, threading, httpx
from typing import List, Dict, Optional
from app.core.config import settings

_rate_lock = threading.Lock()
_rate_window: Dict[str, list] = {}

def _check_rate_limit(key: str, max_per_minute: int = 30) -> bool:
    now = time.time()
    with _rate_lock:
        if key not in _rate_window: _rate_window[key] = []
        _rate_window[key] = [t for t in _rate_window[key] if now - t < 60]
        if len(_rate_window[key]) >= max_per_minute: return False
        _rate_window[key].append(now)
        return True

cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()

def cache_get(key: str):
    with _cache_lock:
        e = cache.get(key)
        if e and time.time() < e[1]: return e[0]
        if e: del cache[key]
    return None

def cache_set(key: str, value, ttl: int = 300):
    with _cache_lock: cache[key] = (value, time.time() + ttl)


class LLMService:
    MIMO_URL = "https://api.xiaomimimo.com/v1/chat/completions"
    MIMO_MODEL = "mimo-v2.5"
    DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
    ZHIPU_VISION_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    def __init__(self):
        self.mimo_key = settings.XIAOMI_API_KEY or os.getenv("XIAOMI_API_KEY", "")
        self.dashscope_key = settings.DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY", "")
        self.deepseek_key = getattr(settings, "DEEPSEEK_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = settings.LLM_MODEL
        self.enabled = bool(self.mimo_key or self.dashscope_key or self.deepseek_key)

    def _call_llm_api(self, url: str, key: str, payload: dict, timeout: float = 30.0) -> Dict:
        h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, headers=h, json=payload)
        if r.status_code == 200:
            d = r.json()
            if d.get("error"): return {"success": False, "error": str(d["error"])}
            choices = d.get("choices", [{}])
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            return {"success": True, "content": content, "usage": d.get("usage", {}), "request_id": d.get("id", "")}
        return {"success": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}

    def _call_with_retry(self, url: str, key: str, payload: dict, timeout: float = 30.0, max_retries: int = 3) -> Dict:
        last = None
        for i in range(max_retries):
            try:
                r = self._call_llm_api(url, key, payload, timeout)
                if r.get("success"): return r
                last = r.get("error", "unknown")
            except httpx.TimeoutException: last = f"timeout ({timeout}s)"
            except Exception as e: last = str(e)
            if i < max_retries - 1: time.sleep(2 ** i)
        return {"success": False, "error": last or "retries exhausted"}

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 2000, provider: str = "auto", enable_search: bool = False) -> Dict:
        if not self.enabled: return self._mock_generate(prompt)
        if not _check_rate_limit("llm", settings.LLM_RATE_LIMIT_PER_MINUTE):
            return {"success": False, "error": "请求过于频繁，请稍后再试"}

        messages = []
        if system_prompt: messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Provider priority
        if provider == "auto":
            order = [
                ("mimo", self.mimo_key, self.MIMO_URL, self.MIMO_MODEL),
                ("dashscope", self.dashscope_key, self.DASHSCOPE_URL, self.model),
                ("deepseek", self.deepseek_key, self.DEEPSEEK_URL, "deepseek-chat"),
            ]
        elif provider == "mimo" and self.mimo_key:
            order = [("mimo", self.mimo_key, self.MIMO_URL, self.MIMO_MODEL)]
        elif provider == "dashscope" and self.dashscope_key:
            order = [("dashscope", self.dashscope_key, self.DASHSCOPE_URL, self.model)]
        elif provider == "deepseek" and self.deepseek_key:
            order = [("deepseek", self.deepseek_key, self.DEEPSEEK_URL, "deepseek-chat")]
        else:
            return {"success": False, "error": f"no available provider: {provider}"}

        last = None
        for name, key, url, model in order:
            if not key: continue
            p = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
            # MiMo web search
            if name == "mimo" and enable_search:
                p["enable_search"] = True
            r = self._call_with_retry(url, key, p, timeout=30.0)
            r["provider"] = name
            if r.get("success"): return r
            last = r.get("error", "unknown")
        return {"success": False, "error": last or "all providers failed"}

    def search_web(self, query: str, max_tokens: int = 500) -> Dict:
        """MiMo 联网搜索 — 适用于需要实时信息的查询"""
        return self.generate_text(query, temperature=0.3, max_tokens=max_tokens, provider="mimo", enable_search=True)

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> Dict:
        """Qwen-VL-OCR 图片文字提取（阿里百炼）"""
        import base64
        if not self.dashscope_key:
            return {"success": False, "error": "DASHSCOPE_API_KEY not set"}

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": "qwen-vl-ocr",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                     "min_pixels": 28 * 28 * 4, "max_pixels": 28 * 28 * 5000},
                    {"type": "text", "text": "Read all the text in the image. Output in markdown format."},
                ]
            }],
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        return self._call_with_retry(self.DASHSCOPE_URL, self.dashscope_key, payload, timeout=60.0)

    def _mock_generate(self, prompt: str) -> Dict:
        return {"success": True, "content": "[MOCK] configure XIAOMI_API_KEY / DASHSCOPE_API_KEY / DEEPSEEK_API_KEY to enable.", "usage": {"input_tokens": len(prompt), "output_tokens": 50}, "request_id": "mock"}

    # ═══════════════════════════════════════════════════
    # AI Generate Questions
    # ═══════════════════════════════════════════════════

    def generate_questions(self, knowledge_points: List[str], difficulty: str, quantity: int = 10, question_types: List[str] = None, rag_context: List[Dict] = None) -> Dict:
        type_map = {'choice': '选择题', 'fill': '填空题', 'calc': '计算题', 'experiment': '实验题', 'inference': '推断题'}
        type_names = [type_map.get(t, t) for t in (question_types or ['choice'])]
        type_desc = '、'.join(type_names)
        active_types = question_types or ['choice']

        type_specs = {
            'choice': {'rules': '4个选项(A/B/C/D)，标注正确选项。设置1-2个陷阱选项。', 'example': '{"content":"下列关于盐类水解的说法正确的是（ ）","type":"choice","options":["A...","B...","C...","D..."],"answer":"A","knowledge_points":["盐类水解"],"difficulty":"medium"}'},
            'fill': {'rules': '题目用___标记填空。答案只填空缺内容。每道题可有1-3个空。不要设选项。', 'example': '{"content":"实验室制氧气的方程式为___，MnO2是___。","type":"fill","answer":"2KClO3=2KCl+3O2(MnO2催化); 催化剂","knowledge_points":["氧气制备"],"difficulty":"medium"}'},
            'calc': {'rules': '具体数值条件。答案含分步计算: 公式→数据→结果→结论。不要设选项。', 'example': '{"content":"5.85g NaCl溶于水配成500mL溶液。求:(1)物质的量(2)浓度。M(NaCl)=58.5g/mol","type":"calc","answer":"(1)n=5.85/58.5=0.10mol (2)c=0.10/0.5=0.20mol/L","knowledge_points":["物质的量浓度"],"difficulty":"medium"}'},
            'experiment': {'rules': '描述化学实验情境(仪器/试剂/操作)。2-3个子问题。不要设选项。', 'example': '{"content":"用右图装置进行铜与浓硫酸反应实验。(1)写方程式(2)品红褪色说明什么(3)棉花蘸NaOH的作用","type":"experiment","answer":"(1)Cu+2H2SO4(浓)=CuSO4+SO2+2H2O (2)SO2 (3)吸收SO2防污染","knowledge_points":["浓硫酸","SO2"],"difficulty":"medium"}'},
            'inference': {'rules': '给出物质转化线索或实验现象，推断未知物质并写方程式。答案含推断过程。不要设选项。', 'example': '{"content":"A、B、C三种常见物质。A黑色粉末与稀硫酸生成蓝色溶液B。B与铁反应析出红色固体C。推断A、B、C并写方程式。","type":"inference","answer":"A:CuO B:CuSO4 C:Cu。CuO+H2SO4=CuSO4+H2O。Fe+CuSO4=FeSO4+Cu","knowledge_points":["金属活动性","置换反应"],"difficulty":"hard"}'},
        }

        type_sections = []
        for qt in active_types:
            if qt in type_specs:
                s = type_specs[qt]
                type_sections.append(f"【{type_map[qt]}】{s['rules']}\nJSON示例: {s['example']}")

        system_prompt = f"""你是资深高中化学教师。

生成: {type_desc}

格式规范（严格遵循）:
{chr(10).join(type_sections)}

核心原则:
1. 科学性100%正确，方程式配平
2. 选择题带options，非选择题不带options
3. 非选择题content必须是该题型的真实内容（不能是选择题去掉选项）
4. 填空题必含___标记。计算题必含分步计算。实验题必含2-3个子问题。

返回纯JSON（无markdown代码块）:
{{"questions":[{{"content":"...","type":"choice","options":["A...","B..."],"answer":"...","knowledge_points":["..."],"difficulty":"medium"}}]}}"""

        if rag_context and len(rag_context) >= 3:
            ctx = "\n\n".join([f"真题{i+1}: {q.get('content','')} 答案:{q.get('answer','')}" for i, q in enumerate(rag_context[:5])])
            prompt = f"基于以下真题生成变种题:\n{ctx}\n生成{quantity}道{difficulty}难度的{type_desc}，直接返回JSON:"
        else:
            prompt = f"为以下知识点生成{quantity}道{difficulty}难度的{type_desc}:\n知识点: {', '.join(knowledge_points)}\n类型从 [{', '.join(active_types)}] 中选择。直接返回JSON:"

        return self.generate_text(prompt, system_prompt, temperature=0.7)

    def audit_question_with_llm(self, question_content: str) -> Dict:
        return self.generate_text(f"审核以下高中化学题目:\n{question_content}\n返回JSON: {{'is_qualified':bool,'issues':['...']}}",
            "你是高中化学教研专家，审核题目的科学性/准确性/适当性。严格审核，发现任何科学性错误必须指出。", temperature=0.3)

    def diagnose_barrier_type(self, student_error_history: List[Dict], question_content: str, student_answer: str, correct_answer: str) -> Dict:
        return self.generate_text(
            f"学生答题情况:\n题目: {question_content}\n学生答案: {student_answer}\n正确答案: {correct_answer}\n历史错误: {json.dumps(student_error_history, ensure_ascii=False)}\n返回JSON: {{'barrier_type':'concept/reading/expression','confidence':0.8,'reasoning':'...','suggestion':'...'}}",
            "你是教育心理学专家。分析学生障碍类型: concept(概念理解偏差)/reading(审题信息不全)/expression(无法规范表述)。", temperature=0.3)

    def generate_learning_plan(self, student_name: str, barrier_type: str, weak_knowledge_points: List[str], recent_performance: Optional[Dict] = None) -> Dict:
        bd = {"concept": "概念理解型-概念理解偏差", "reading": "审题障碍型-读取信息不全", "expression": "表述障碍型-无法规范表述"}.get(barrier_type, barrier_type)
        return self.generate_text(f"为学生{student_name}生成学习计划:\n障碍类型: {bd}\n薄弱知识点: {', '.join(weak_knowledge_points) if weak_knowledge_points else '暂无'}\n返回JSON: {{'plan_title':'标题','plan_period':'2周','daily_tasks':[...],'weekly_goals':[...],'barrier_interventions':[...],'motivation_tips':[...]}}",
            "你是资深高中化学教师，根据学生障碍和薄弱点制定个性化学习计划。计划需具体可执行。", temperature=0.7)

    def analyze_paper_with_vision(self, image_data: str, paper_type: str = "mixed") -> Dict:
        prompt = self._get_vision_prompt(paper_type)
        mime = self._detect_image_mime(image_data)
        messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}}, {"type": "text", "text": prompt}]}]

        # MiMo first (native vision)
        if self.mimo_key:
            try:
                r = self._call_with_retry(self.MIMO_URL, self.mimo_key, {"model": self.MIMO_MODEL, "messages": messages, "temperature": 0.1, "max_tokens": 2000}, timeout=120.0, max_retries=2)
                if r.get("success"): return self._parse_vision_response(r.get("content", ""))
            except Exception: pass

        # ZhiPu fallback
        zk = os.getenv("ZHIPU_API_KEY", "") or settings.ZHIPU_API_KEY
        if zk:
            try:
                r = self._call_with_retry(self.ZHIPU_VISION_URL, zk, {"model": "glm-4v", "messages": messages, "temperature": 0.1, "max_tokens": 2000}, timeout=120.0, max_retries=2)
                if r.get("success"): return self._parse_vision_response(r.get("content", ""))
                return {"success": False, "error": r.get("error", "Vision API failed"), "message": "多模态分析失败"}
            except Exception as e: return {"success": False, "error": str(e), "message": "多模态分析异常"}

        return {"success": False, "error": "无可用视觉模型", "message": "请配置 MiMo 或 智谱 API Key"}

    def _get_vision_prompt(self, pt: str) -> str:
        return {"answer_sheet": "分析答题卡图片，识别学号、姓名、每题答案(A/B/C/D)。返回JSON: {\"student_id\":\"\",\"student_name\":\"\",\"questions\":[{\"number\":\"1\",\"student_answer\":\"A\"}],\"message\":\"\"}",
                "printed": "分析印刷试卷图片，识别标题、所有题目内容和选项、标准答案。返回JSON: {\"title\":\"\",\"questions\":[{\"number\":\"1\",\"content\":\"\",\"options\":[\"A\",\"B\"],\"correct_answer\":\"A\"}]}",
                "handwritten": "分析手写试卷图片，识别姓名、手写题目内容、作答内容。返回JSON: {\"student_name\":\"\",\"questions\":[{\"number\":\"1\",\"content\":\"\",\"student_answer\":\"\"}]}",
                "mixed": "分析混合试卷图片(印刷题目+手写作答)，识别学号、姓名、印刷题目、手写作答。返回JSON: {\"student_id\":\"\",\"student_name\":\"\",\"questions\":[{\"number\":\"1\",\"content\":\"\",\"options\":[],\"student_answer\":\"\"}]}"}.get(pt, "分析试卷图片，提取所有题目信息和作答内容。")

    def _detect_image_mime(self, data: str) -> str:
        try:
            raw = base64.b64decode(data[:24])
            if raw[:4] == b'\x89PNG': return "image/png"
            if raw[:3] == b'\xff\xd8\xff': return "image/jpeg"
        except: pass
        return "image/png"

    def _parse_vision_response(self, content: str) -> Dict:
        try:
            for d in ("```json", "```"):
                if d in content:
                    parts = content.split(d)
                    content = parts[1].split("```")[0] if len(parts) > 1 else content
                    break
            data = json.loads(content.strip())
            return {"success": True, "student_id": data.get("student_id", ""), "student_name": data.get("student_name", ""), "questions": data.get("questions", []), "raw_text": content, "message": data.get("message", "识别完成")}
        except json.JSONDecodeError:
            return {"success": True, "student_id": "", "student_name": "", "questions": [], "raw_text": content, "message": "识别完成，请查看原始文本"}


class ChatGLMService:
    def __init__(self): self.api_url = os.getenv("CHATGLM_API_URL", "http://localhost:8001"); self.enabled = False
    def generate_text(self, prompt: str, **kw) -> Dict:
        if not self.enabled: return {"success": False, "error": "ChatGLM not enabled"}
        try:
            import httpx as hx
            r = hx.post(self.api_url, json={"prompt": prompt, **kw}, timeout=30.0)
            return {"success": True, "content": r.json().get("response", "")} if r.status_code == 200 else {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e: return {"success": False, "error": str(e)}


llm_service = LLMService()
chatglm_service = ChatGLMService()
