# 智辅化学 (ChemAI) - 前端

高中化学AI辅助教学工具完整前端，包含登录、教师端、学生端

## 设计风格

**Neo-Laboratory（未来实验室）**

- 深色背景配合霓虹化学色彩
- 分子结构动画背景
- 毛玻璃效果卡片
- 精致的微交互和动画

### 色彩系统

| 用途 | 颜色 |
|------|------|
| 主色 | `#00d4aa` (青色) |
| 障碍-概念 | `#f59e0b` (琥珀) |
| 障碍-审题 | `#00d4aa` (青色) |
| 障碍-表述 | `#a855f7` (紫色) |
| 背景 | `#070a0d` (深蓝灰) |

### 字体

- 标题：`Noto Serif SC`
- 正文：`Outfit`
- 数据：`JetBrains Mono`

## 文件结构

```
frontend/
├── login.html      # 登录/注册页面
├── teacher.html    # 教师端工作台
├── student.html     # 学生端移动App
├── styles.css      # 共享样式表
├── app.js          # 共享JavaScript
└── README.md       # 说明文档
```

## 启动方式

### 教师端

```bash
# 方式一：直接在浏览器打开
open teacher.html

# 方式二：本地服务器
cd frontend
python -m http.server 3000
# 访问 http://localhost:3000/teacher.html
```

### 学生端

```bash
# 直接在浏览器打开
open student.html

# 或通过服务器
# 访问 http://localhost:3000/student.html
```

### 登录页

```bash
# 访问 http://localhost:3000/login.html

# 演示账号：
# 教师：teacher / teacher123
# 学生：student / student123
```

## 功能模块

### 登录页 (login.html)

- [x] 登录/注册表单切换
- [x] 表单验证
- [x] 密码显示/隐藏
- [x] 验证码发送
- [x] 角色快速入口
- [x] 分子动画背景
- [x] 演示模式提示

### 教师端 (teacher.html)

#### 首页
- [x] 今日问候
- [x] 快速统计卡片
- [x] 近期考试列表
- [x] 班级障碍分布图

#### 错题统计 (F1)
- [x] 答题卡上传区
- [x] 拖拽上传
- [x] 历史记录表格
- [x] OCR识别提示

#### 出题 (F2)
- [x] AI出题/手动选题切换
- [x] 知识点多选
- [x] 难度选择
- [x] 题量调节
- [x] 历年真题库
- [x] 三维安全审核结果展示

#### 报告 (F3)
- [x] 老师详情版/学生筛选版切换
- [x] 报告预览
- [x] 高频错题表格
- [x] 障碍分布图
- [x] 一键发送全班

#### 障碍诊断 (F4)
- [x] 三类障碍规则配置
- [x] 阈值调节
- [x] 掌握标准配置
- [x] 学生诊断预览

#### 学情面板 (F7)
- [x] 班级平均分趋势
- [x] 知识点掌握情况
- [x] 进步榜

### 学生端 (student.html)

#### 首页
- [x] 班级排名卡片
- [x] 今日任务列表
- [x] 进步趋势图
- [x] 障碍类型分布

#### 练习
- [x] 题目展示
- [x] 选项选择
- [x] 答案确认
- [x] 对错反馈
- [x] 知识点解析
- [x] 易错提示

#### 错题本 (S3)
- [x] 错题列表
- [x] 掌握状态
- [x] 还需练习次数

#### 报告 (练习后)
- [x] 正确率统计
- [x] 用时统计
- [x] 障碍类型变化

#### 我的
- [x] 个人资料
- [x] 学习统计
- [x] 设置入口

## 后端对接

前端默认连接 `http://localhost:8000/api`

### API 端点

| 功能 | 端点 | 方法 |
|------|------|------|
| OCR识别 | `/api/ocr` | POST |
| 考试列表 | `/api/exam/list/{class_id}` | GET |
| AI出题 | `/api/question/generate` | POST |
| 历年真题 | `/api/question/historical` | GET |
| 手动选题 | `/api/question/manual/select` | POST |
| 老师报告 | `/api/report/teacher/{exam_id}` | GET |
| 学生报告 | `/api/report/student/{exam_id}/{student_id}` | GET |
| 发送报告 | `/api/report/send-to-students/{exam_id}` | POST |
| 障碍诊断 | `/api/diagnosis/barrier/{class_id}/{exam_id}` | GET |
| 诊断配置 | `/api/diagnosis/config/{teacher_id}` | GET/PUT |
| 学情面板 | `/api/panel/class/{class_id}` | GET |
| 布置练习 | `/api/practice/assign` | POST |
| 学生任务 | `/api/practice/student/{student_id}/tasks` | GET |
| 提交练习 | `/api/practice/submit` | POST |

## 浏览器兼容

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## License

内部使用 - 智辅化学 ChemAI
