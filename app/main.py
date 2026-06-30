"""
ChemAI Main Application
基于FastAPI的高中化学AI辅助教学工具后端服务
"""
import os
import json as json_lib

# 禁用 ChromaDB posthog telemetry (修复版本兼容性问题)
try:
    import posthog
    _original_capture = posthog.capture
    posthog.capture = lambda *args, **kwargs: None
except ImportError:
    pass

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from app.core.config import settings

# ── 铁律：全局化学式渲染 — 所有 JSON 响应中的化学式自动转 Unicode 下标/上标 ──
from app.utils.chem_render import render_chem_deep
_original_json_render = JSONResponse.render
def _patched_render(self, content):
    return _original_json_render(self, render_chem_deep(content))
JSONResponse.render = _patched_render

# API路由
from app.api import ocr, exam, question, diagnosis, report, practice, panel, auth, user, class_api, exam_bank, memory, school, grade, teacher_application, log, parent, review, warning, analytics, integration, notification, knowledge
from app.api.practice_api import wrong_topic
from app.mcp import mcp_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="高中化学AI辅助教学工具 - 教师端+学生端API服务"
)

# 获取前端文件目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# CORS配置（生产环境通过 CHEMAI_CORS_ORIGINS 环境变量设置白名单）
ALLOWED_ORIGINS = os.getenv("CHEMAI_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS.split(",") if ALLOWED_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 无需认证的路径
PUBLIC_PREFIXES = ["/api/auth/", "/api/agent/", "/api/ocr/", "/api/classes", "/docs", "/redoc", "/openapi.json", "/health", "/api/knowledge/", "/api/exam-bank/", "/api/question/"]
PUBLIC_EXTENSIONS = {".html", ".js", ".css", ".png", ".ico", ".svg", ".woff2"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # 非 API 路径跳过
    if not path.startswith("/api/"):
        return await call_next(request)
    # 白名单前缀跳过（如 /api/auth/、/api/agent/ 及其子路径）
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)
    # 静态文件跳过
    if any(path.endswith(ext) for ext in PUBLIC_EXTENSIONS):
        return await call_next(request)

    from app.middleware.auth import verify_token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "未携带认证token"})
    token = auth_header.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        return JSONResponse(status_code=401, content={"detail": "token无效或已过期"})
    return await call_next(request)

# 注册API路由（优先级最高）
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(user.router, prefix="/api/users", tags=["用户管理"])
app.include_router(class_api.router, prefix="/api/classes", tags=["班级管理"])
app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR识别"])
app.include_router(exam.router, prefix="/api/exam", tags=["考试管理"])
app.include_router(question.router, prefix="/api/question", tags=["题目管理"])
app.include_router(diagnosis.router, prefix="/api/diagnosis", tags=["障碍诊断"])
app.include_router(report.router, prefix="/api/report", tags=["报告生成"])
app.include_router(practice.router, prefix="/api/practice", tags=["自适应练习"])
app.include_router(panel.router, prefix="/api/panel", tags=["学情面板"])
app.include_router(exam_bank.router, prefix="/api/exam-bank", tags=["真题库管理"])
app.include_router(memory.router, prefix="/api/memory", tags=["学情记忆"])
app.include_router(school.router, prefix="/api/school", tags=["学校设置"])
app.include_router(grade.router, prefix="/api/grades", tags=["年级管理"])
app.include_router(teacher_application.router, prefix="/api/teacher-applications", tags=["教师入驻"])
app.include_router(log.router, prefix="/api/logs", tags=["操作日志"])
app.include_router(parent.router, prefix="/api/parent", tags=["家长端"])
app.include_router(review.router, prefix="/api/review", tags=["间隔复习"])
app.include_router(warning.router, prefix="/api/warning", tags=["学情预警"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据可视化"])
app.include_router(integration.router, prefix="/api/integration", tags=["LMS集成"])
app.include_router(notification.router, prefix="/api/notification", tags=["通知推送"])
app.include_router(wrong_topic.router, prefix="/api/practice/wrong-topic", tags=["错题强化"])
app.include_router(mcp_router, tags=["MCP工具"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识卡片"])

# ChemAgent (pydantic-ai, deprecated — replaced by langgraph)
from agent.channel.fastapi_sse import router as agent_router
app.include_router(agent_router, prefix="/api/agent", tags=["AI Agent"])

# ChemAgent (LangGraph ReAct agent)
from agent.channel.langgraph_channel import router as langgraph_router
app.include_router(langgraph_router, prefix="/api/agent", tags=["AI Agent (LangGraph)"])


def _nocache_file(path, **kw):
    """返回文件并禁用缓存"""
    from starlette.responses import FileResponse as _FR
    resp = _FR(path, **kw)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.get("/")
async def root():
    html_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(html_file):
        return _nocache_file(html_file)
    return RedirectResponse(url="/login.html")

@app.get("/m")
async def mobile_root():
    return RedirectResponse(url="/m/index.html")


# 真题题库图片静态文件
from fastapi.staticfiles import StaticFiles
import os as _os
_figures_dir = _os.path.join(_os.path.dirname(__file__), "..", "data", "exam_questions")
if _os.path.isdir(_figures_dir):
    app.mount("/static/figures", StaticFiles(directory=_figures_dir), name="figures")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# 静态文件路由（精确匹配，避免被动态路由捕获）
@app.get("/app.js")
async def serve_app_js():
    js_file = os.path.join(FRONTEND_DIR, "app.js")
    if os.path.exists(js_file):
        return FileResponse(js_file, media_type="application/javascript")
    return RedirectResponse(url="/")


@app.get("/components/{file}")
async def serve_component(file: str):
    """前端组件静态文件"""
    file_path = os.path.join(FRONTEND_DIR, "components", file)
    if os.path.exists(file_path):
        ext = file.rsplit(".", 1)[-1] if "." in file else ""
        media_types = {"js": "application/javascript", "css": "text/css"}
        return FileResponse(file_path, media_type=media_types.get(ext))
    return RedirectResponse(url="/")

@app.get("/styles.css")
async def serve_css():
    css_file = os.path.join(FRONTEND_DIR, "styles.css")
    if os.path.exists(css_file):
        return FileResponse(css_file, media_type="text/css")
    return RedirectResponse(url="/")


@app.get("/common.css")
async def serve_common_css():
    css_file = os.path.join(FRONTEND_DIR, "common.css")
    if os.path.exists(css_file):
        return FileResponse(css_file, media_type="text/css")
    return RedirectResponse(url="/")


@app.get("/login.html")
async def serve_login_html():
    html_file = os.path.join(FRONTEND_DIR, "login.html")
    if os.path.exists(html_file):
        return _nocache_file(html_file)
    return RedirectResponse(url="/")


@app.get("/index.html")
async def serve_index_html():
    html_file = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(html_file):
        html_file = os.path.join(FRONTEND_DIR, "login.html")
    return FileResponse(html_file)


# 前端静态资源精确路由（必须在兜底 /{page} 之前）
@app.get("/design-system.css")
async def serve_design_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "design-system.css"))

@app.get("/js/{filename}")
async def serve_js(filename: str):
    fp = os.path.join(FRONTEND_DIR, "js", filename)
    if os.path.isfile(fp):
        return FileResponse(fp)
    raise HTTPException(status_code=404)

@app.get("/pages/{filename}")
async def serve_pages(filename: str):
    fp = os.path.join(FRONTEND_DIR, "pages", filename)
    if os.path.isfile(fp):
        return FileResponse(fp)

@app.get("/m/{filename}")
async def serve_mobile(filename: str):
    fp = os.path.join(FRONTEND_DIR, "m", filename)
    if os.path.isfile(fp):
        return _nocache_file(fp)
    return RedirectResponse(url="/m/index.html")
    raise HTTPException(status_code=404)

# HTML页面路由（兜底 — 必须放在所有精确路由之后）
@app.get("/{page}")
async def serve_page(page: str):
    if ".." in page or page.startswith("/"):
        return RedirectResponse(url="/")
    # 如果已经是完整文件名（如 teacher.html），直接用
    if page.endswith(".html"):
        candidates = [
            os.path.join(FRONTEND_DIR, page),
            os.path.join(FRONTEND_DIR, "pages", page),
        ]
    else:
        candidates = [
            os.path.join(FRONTEND_DIR, f"{page}.html"),
            os.path.join(FRONTEND_DIR, "pages", f"{page}.html"),
        ]
    for html_file in candidates:
        if os.path.exists(html_file):
            return _nocache_file(html_file)
    return RedirectResponse(url="/")


@app.on_event("startup")
async def startup_event():
    from app.models.database import engine, Base
    from app.models.database import get_session_factory
    Base.metadata.create_all(bind=engine)
    print("数据库表已创建/验证")

    from app.utils.init_db import init_database
    init_database()

    # 注册 Agent Skills
    try:
        from agent.skills_init import register_all_skills
        register_all_skills()
    except Exception as e:
        print(f"Skills 注册失败: {e}")

    # 启动调度器
    try:
        from app.scheduler import init_scheduler
        init_scheduler(app)
    except ImportError as e:
        print(f"调度器启动失败 (APScheduler可能未安装): {e}")


@app.on_event("shutdown")
async def shutdown_event():
    # 关闭调度器
    try:
        from app.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception as e:
        print(f"调度器关闭失败: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
