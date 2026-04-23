"""
ChemAI Main Application
基于FastAPI的高中化学AI辅助教学工具后端服务
"""
import os

# 禁用 ChromaDB posthog telemetry (修复版本兼容性问题)
try:
    import posthog
    _original_capture = posthog.capture
    posthog.capture = lambda *args, **kwargs: None
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from app.core.config import settings

# API路由
from app.api import ocr, exam, question, diagnosis, report, practice, panel, auth, user, class_api, exam_bank, memory, school, grade, teacher_application, log

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="高中化学AI辅助教学工具 - 教师端+学生端API服务"
)

# 获取前端文件目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/")
async def root():
    # 直接跳转到登录页面
    return RedirectResponse(url="/login.html")


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


@app.get("/styles.css")
async def serve_css():
    css_file = os.path.join(FRONTEND_DIR, "styles.css")
    if os.path.exists(css_file):
        return FileResponse(css_file, media_type="text/css")
    return RedirectResponse(url="/")


@app.get("/login.html")
async def serve_login_html():
    html_file = os.path.join(FRONTEND_DIR, "login.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    return RedirectResponse(url="/")


@app.get("/teacher.html")
async def serve_teacher_html():
    html_file = os.path.join(FRONTEND_DIR, "teacher.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    return RedirectResponse(url="/")


@app.get("/student.html")
async def serve_student_html():
    html_file = os.path.join(FRONTEND_DIR, "student.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    return RedirectResponse(url="/")


@app.get("/index.html")
async def serve_index_html():
    html_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    return RedirectResponse(url="/")


# HTML页面路由（兜底）
@app.get("/{page}")
async def serve_page(page: str):
    if ".." in page or page.startswith("/"):
        return RedirectResponse(url="/")
    # 如果已经是完整文件名（如 teacher.html），直接用
    if page.endswith(".html"):
        html_file = os.path.join(FRONTEND_DIR, page)
    else:
        html_file = os.path.join(FRONTEND_DIR, f"{page}.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    return RedirectResponse(url="/")


@app.on_event("startup")
async def startup_event():
    from app.models.database import engine, Base
    from app.models.database import get_session_factory
    Base.metadata.create_all(bind=engine)
    print("数据库表已创建/验证")

    from app.utils.init_db import init_database
    init_database()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
