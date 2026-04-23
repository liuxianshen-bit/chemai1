# ChemAI 版本文档

## 版本管理策略

本文档记录 ChemAI 系统的所有版本变更，用于追踪功能和确保可回滚性。

---

## v1.0.0 - 2026-04-23

### 初始版本 - 邵阳县第一中学演示数据完成

#### 新增功能

**数据层**
- 邵阳县第一中学演示数据 (shaoyang_001)
- 3个年级：高一、高二、高三
- 2个班级：高一(1)班34人、高一(2)班33人
- 66名学生（学号202610101~202610233）
- 3名教师：海老师(学科组长)、刘老师、陈老师
- 13个考试记录
- 324道题目（含31道大题）
- 9600条答题记录
- 障碍类型分布：concept(709)/reading(1013)/expression(585)

**认证系统**
- JWT token认证
- 4个角色：admin、学科组长、teacher、student
- 账号体系：
  - admin / admin123 (系统管理员)
  - hai / hai123456 (学科组长)
  - liu / 123456 (任课教师)
  - chen / 123456 (任课教师)
  - 202610101~202610233 / 123456 (学生)

**API模块**
- 班级管理：GET/PUT/DELETE /api/classes
- 学生管理：获取班级学生列表
- OCR识别：/api/ocr 系列端点
- 学情诊断：/api/diagnosis/barrier/{class_id}/{exam_record_id}
- 学习计划：/api/diagnosis/learning-plan/generate

**测试数据**
- 128个示例答题卡（64 PNG + 64 PDF）
  - clean（整洁）：16组
  - normal（一般）：16组
  - messy（潦草）：16组
  - very_messy（非常潦草）：16组

**文件结构**
```
chemai-backend/
├── app/
│   ├── api/           # API路由
│   │   ├── auth.py
│   │   ├── class_api.py
│   │   ├── diagnosis.py
│   │   ├── ocr.py
│   │   └── ...
│   ├── middleware/    # 中间件
│   ├── models/        # 数据模型
│   └── utils/         # 工具脚本
│       ├── init_db.py           # 数据库初始化
│       ├── import_exam_data.py  # 考试数据导入
│       ├── generate_large_questions.py  # 大题生成
│       └── create_sample_answer_sheets.py  # 答题卡生成
├── data/
│   ├── exam_questions/   # 历史真题 (250+题)
│   ├── knowledge_graph/  # 知识图谱 (50+知识点)
│   └── sample_answer_sheets/  # 示例答题卡 (128文件)
├── frontend/          # 前端资源
└── TEST_PLAN.md      # 测试计划
```

#### 测试状态
- [x] 数据验证测试 PASS
- [x] 认证模块测试 PASS
- [x] 班级管理测试 PASS
- [x] OCR识别测试 PASS
- [x] 学情诊断测试 PASS
- [x] 学习计划测试 PASS

#### 已知问题
- 无

---

## 版本回滚指南

### 回滚命令

```bash
# 查看版本历史
git log --oneline

# 回滚到指定版本
git reset --hard <commit-hash>

# 回滚到v1.0.0
git reset --hard v1.0.0
```

### 版本标签

| 标签 | 日期 | 说明 |
|------|------|------|
| v1.0.0 | 2026-04-23 | 初始版本 |

---

## 后续迭代说明

每次重要更新后：
1. 创建新的版本条目
2. 记录新增/修改/删除的功能
3. 更新测试状态
4. 使用 `git tag` 标记版本

---

*最后更新：2026-04-23*
