/**
 * 教师端 - 题目管理模块
 * 使用 Hermes Agent 实现真正的 AI 出题
 */
import { questionService } from '../../services/index.js'
import { hermesService, TaskType } from '../../services/hermes.js'
import { Toast, showLoading, hideLoading, showHermesThinking, hideHermesThinking } from '../../components/index.js'

// 全局状态
let currentQuestionList = []
let currentFilter = {}

/**
 * 初始化题目模块
 */
export async function initQuestionModule() {
  const container = document.getElementById('question-container')
  if (!container) return

  await loadQuestionList()
}

/**
 * 加载题目列表
 */
export async function loadQuestionList(filter = {}) {
  const container = document.getElementById('exam-bank-list')
  if (!container) return

  showLoading('加载题目...')

  try {
    currentFilter = filter
    const result = await questionService.getQuestionList(filter)

    if (result.success) {
      currentQuestionList = result.data || []
      renderQuestionList(currentQuestionList)
    } else {
      Toast.error('加载题目列表失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 渲染题目列表
 */
function renderQuestionList(questions) {
  const container = document.getElementById('exam-bank-list')
  if (!container) return

  if (questions.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-size:3rem;margin-bottom:16px;">📚</div>
        <p>暂无题目</p>
        <button class="btn-primary" onclick="showGenerateQuestionModal()">生成新题目</button>
      </div>
    `
    return
  }

  container.innerHTML = questions.map(question => `
    <div class="question-card" data-id="${question.id}">
      <div class="question-header">
        <span class="question-type type-${question.type}">${getQuestionTypeName(question.type)}</span>
        <span class="question-difficulty difficulty-${question.difficulty}">${getDifficultyName(question.difficulty)}</span>
      </div>
      <div class="question-content">
        ${question.content || question.title}
      </div>
      <div class="question-meta">
        <span>知识点: ${(question.knowledge_points || []).join(', ')}</span>
      </div>
      <div class="question-actions">
        <button class="btn-secondary" onclick="viewQuestionDetail('${question.id}')">查看</button>
        <button class="btn-secondary" onclick="editQuestion('${question.id}')">编辑</button>
        <button class="btn-danger" onclick="deleteQuestion('${question.id}')">删除</button>
      </div>
    </div>
  `).join('')
}

/**
 * 获取题目类型名称
 */
function getQuestionTypeName(type) {
  const names = {
    choice: '选择题',
    fill_blank: '填空题',
    judgment: '判断题',
    short_answer: '简答题',
    calculation: '计算题'
  }
  return names[type] || type
}

/**
 * 获取难度名称
 */
function getDifficultyName(difficulty) {
  const names = {
    easy: '简单',
    medium: '中等',
    hard: '困难'
  }
  return names[difficulty] || difficulty
}

/**
 * 显示生成题目弹窗
 */
export function showGenerateQuestionModal() {
  const modal = document.getElementById('question-generate-modal')
  if (!modal) return

  // 重置表单
  const form = document.getElementById('question-generate-form')
  if (form) form.reset()

  modal.style.display = 'flex'
}

/**
 * 生成题目（使用 Hermes Agent）
 */
export async function generateQuestions(params) {
  // 显示 Hermes Agent 流式界面
  showHermesThinking({
    task: TaskType.GENERATE_QUESTIONS,
    message: '正在生成题目...',
    onCancel: () => {
      hermesService.cancel()
      Toast.info('已取消生成')
    }
  })

  try {
    // 使用 Hermes Agent 执行题目生成
    const result = await runQuestionGeneration(params)

    hideHermesThinking()

    if (result.success) {
      Toast.success(`成功生成 ${result.data.length} 道题目`)
      closeGenerateModal()
      loadQuestionList()

      if (result.data.length > 0) {
        showGenerateResult(result.data)
      }
    } else {
      Toast.error(result.message || '生成失败')
    }
  } catch (error) {
    hideHermesThinking()
    Toast.error('生成失败：' + error.message)
  }
}

/**
 * 使用 Hermes Agent 执行题目生成（流式）
 */
async function runQuestionGeneration(params) {
  return new Promise((resolve, reject) => {
    let hasReturned = false
    let generatedQuestions = []

    // 设置事件回调
    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking:', event.content)
    })

    hermesService.on('tool_call', (event) => {
      console.log('Hermes tool call:', event.tool, event.params)
    })

    hermesService.on('tool_result', (event) => {
      // 收集生成的题目
      if (event.result?.questions) {
        generatedQuestions = [...generatedQuestions, ...event.result.questions]
      }
    })

    hermesService.on('needs_confirmation', (event) => {
      console.log('Hermes needs confirmation:', event)
      // 题目可能需要审核确认
      if (event.confirmType === 'question_audit' && event.data) {
        showGenerateResult(event.data.questions || [])
      }
    })

    hermesService.on('final', (event) => {
      if (!hasReturned) {
        hasReturned = true
        const questions = event.result?.questions || generatedQuestions
        resolve({
          success: true,
          data: questions
        })
      }
    })

    hermesService.on('error', (event) => {
      if (!hasReturned) {
        hasReturned = true
        reject(new Error(event.error || event.message || 'Agent执行失败'))
      }
    })

    // 执行流式任务
    const streamResult = hermesService.executeStream(TaskType.GENERATE_QUESTIONS, params)

    if (!streamResult.success) {
      reject(new Error(streamResult.error || 'Agent启动失败'))
      return
    }

    // 处理流式响应
    hermesService.processStream(streamResult.reader, (event) => {
      // 事件会在回调中处理
    }).catch((error) => {
      if (!hasReturned) {
        hasReturned = true
        reject(error)
      }
    })
  })
}

/**
 * 显示生成结果
 */
function showGenerateResult(questions) {
  const modal = document.getElementById('question-result-modal')
  if (!modal) return

  const container = document.getElementById('question-result-list')
  if (container) {
    container.innerHTML = questions.map(q => `
      <div class="result-question">
        <div class="question-type">${getQuestionTypeName(q.type)}</div>
        <div class="question-content">${q.content || q.title}</div>
        <div class="question-answer">正确答案: ${q.correct_answer}</div>
        ${q.knowledge_points?.length ? `<div class="question-kps">知识点: ${q.knowledge_points.join(', ')}</div>` : ''}
      </div>
    `).join('')
  }

  modal.style.display = 'flex'
}

/**
 * 审核题目
 */
export async function auditQuestion(questionId, approved, feedback) {
  showLoading()

  try {
    const result = await questionService.auditQuestion(questionId, { approved, feedback })

    if (result.success) {
      Toast.success(approved ? '已通过' : '已拒绝')
      await loadQuestionList(currentFilter)
    } else {
      Toast.error(result.message || '审核失败')
    }
  } catch (error) {
    Toast.error('审核失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 删除题目
 */
export async function deleteQuestion(questionId) {
  if (!confirm('确定要删除这道题目吗？')) return

  showLoading()

  try {
    const result = await questionService.deleteQuestion(questionId)

    if (result.success) {
      Toast.success('删除成功')
      await loadQuestionList(currentFilter)
    } else {
      Toast.error(result.message || '删除失败')
    }
  } catch (error) {
    Toast.error('删除失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 查看题目详情
 */
export function viewQuestionDetail(questionId) {
  const question = currentQuestionList.find(q => q.id === questionId)
  if (!question) return

  const modal = document.getElementById('question-detail-modal')
  if (!modal) return

  const content = document.getElementById('question-detail-content')
  if (content) {
    content.innerHTML = `
      <div class="detail-header">
        <span class="question-type type-${question.type}">${getQuestionTypeName(question.type)}</span>
        <span class="question-difficulty difficulty-${question.difficulty}">${getDifficultyName(question.difficulty)}</span>
      </div>
      <div class="detail-section">
        <h4>题目内容</h4>
        <p>${question.content || question.title}</p>
      </div>
      ${question.options ? `
        <div class="detail-section">
          <h4>选项</h4>
          <div class="options-list">
            ${question.options.map((opt, i) => `
              <div class="option-item ${opt === question.correct_answer ? 'correct' : ''}">
                ${String.fromCharCode(65 + i)}. ${opt}
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
      <div class="detail-section">
        <h4>正确答案</h4>
        <p class="correct-answer">${question.correct_answer}</p>
      </div>
      <div class="detail-section">
        <h4>知识点</h4>
        <p>${(question.knowledge_points || []).join(', ')}</p>
      </div>
      ${question.explanation ? `
        <div class="detail-section">
          <h4>解析</h4>
          <p>${question.explanation}</p>
        </div>
      ` : ''}
    `
  }

  modal.style.display = 'flex'
}

/**
 * 关闭生成弹窗
 */
export function closeGenerateModal() {
  const modal = document.getElementById('question-generate-modal')
  if (modal) modal.style.display = 'none'
}

/**
 * 关闭详情弹窗
 */
export function closeQuestionDetailModal() {
  const modal = document.getElementById('question-detail-modal')
  if (modal) modal.style.display = 'none'
}

/**
 * 关闭结果弹窗
 */
export function closeResultModal() {
  const modal = document.getElementById('question-result-modal')
  if (modal) modal.style.display = 'none'
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.showGenerateQuestionModal = showGenerateQuestionModal
  window.generateQuestions = generateQuestions
  window.auditQuestion = auditQuestion
  window.deleteQuestion = deleteQuestion
  window.viewQuestionDetail = viewQuestionDetail
  window.closeGenerateModal = closeGenerateModal
  window.closeQuestionDetailModal = closeQuestionDetailModal
  window.closeResultModal = closeResultModal
}
