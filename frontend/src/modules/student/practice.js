/**
 * 学生端 - 练习模块
 */
import { practiceService, diagnosisService } from '../../services/index.js'
import { Toast, showLoading, hideLoading, setButtonLoading } from '../../components/index.js'
import { showLearningPlanModal, loadStudentLearningPlan } from './learning_plan.js'

// 全局状态
let currentPractice = null
let currentQuestions = []
let currentAnswers = {}
let currentQuestionIndex = 0

/**
 * 初始化练习模块
 */
export async function initPracticeModule() {
  const container = document.getElementById('practice-container')
  if (!container) return

  await loadPracticeTasks()
}

/**
 * 加载练习任务列表
 */
export async function loadPracticeTasks() {
  const container = document.getElementById('practice-tasks-list')
  if (!container) return

  showLoading('加载练习任务...')

  try {
    const studentId = authService.getCurrentUserFromSession()?.id
    const result = await practiceService.getStudentTasks(studentId)

    if (result.success) {
      renderPracticeTasks(result.data.tasks || [])
    } else {
      Toast.error('加载失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 渲染练习任务列表
 */
function renderPracticeTasks(tasks) {
  const container = document.getElementById('practice-tasks-list')
  if (!container) return

  if (tasks.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-size:3rem;margin-bottom:16px;">📝</div>
        <p>暂无练习任务</p>
        <button class="btn-primary" onclick="loadHistoricalQuestions()">查看历史真题</button>
      </div>
    `
    return
  }

  container.innerHTML = tasks.map(task => `
    <div class="practice-card" onclick="startPractice('${task.practice_id}')">
      <div class="practice-card-header">
        <h3>${getTaskTitle(task)}</h3>
        <span class="status ${task.status}">${getStatusText(task.status)}</span>
      </div>
      <div class="practice-meta">
        <span>知识点: ${(task.knowledge_points || []).join(', ')}</span>
      </div>
      <div class="practice-progress">
        <div class="practice-progress-bar" style="width: ${getProgress(task)}%"></div>
      </div>
      <div class="practice-footer">
        <span>截止时间: ${formatDate(task.deadline)}</span>
        ${task.status === 'pending' ? '<button class="btn-primary btn-sm">开始练习</button>' : ''}
      </div>
    </div>
  `).join('')
}

/**
 * 开始练习
 */
export async function startPractice(practiceId) {
  showLoading('加载题目...')

  try {
    const result = await practiceService.getPracticeQuestions(practiceId)

    if (result.success) {
      currentPractice = result.data
      currentQuestions = result.data.questions || []
      currentAnswers = {}
      currentQuestionIndex = 0

      renderPracticePage()
    } else {
      Toast.error('加载失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 渲染练习页面
 */
function renderPracticePage() {
  const container = document.getElementById('practice-container')
  if (!container) return

  if (currentQuestions.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>暂无题目</p>
      </div>
    `
    return
  }

  container.innerHTML = `
    <div class="practice-page">
      <div class="practice-header">
        <div class="practice-progress-info">
          <span>第 ${currentQuestionIndex + 1} / ${currentQuestions.length} 题</span>
        </div>
        <div class="practice-progress-bar">
          <div class="progress-fill" style="width: ${((currentQuestionIndex + 1) / currentQuestions.length * 100)}%"></div>
        </div>
      </div>

      <div class="question-box" id="question-box">
        <!-- 动态加载 -->
      </div>

      <div class="practice-actions">
        ${currentQuestionIndex > 0 ? '<button class="btn-secondary" onclick="prevQuestion()">上一题</button>' : ''}
        ${currentQuestionIndex < currentQuestions.length - 1
          ? '<button class="btn-primary" onclick="nextQuestion()">下一题</button>'
          : '<button class="btn-success" onclick="submitPractice()">提交练习</button>'}
      </div>
    </div>
  `

  renderCurrentQuestion()
}

/**
 * 渲染当前题目
 */
function renderCurrentQuestion() {
  const container = document.getElementById('question-box')
  if (!container || !currentQuestions[currentQuestionIndex]) return

  const question = currentQuestions[currentQuestionIndex]
  const savedAnswer = currentAnswers[question.question_id]

  container.innerHTML = `
    <div class="question-number">${currentQuestionIndex + 1}</div>
    <div class="question-content">${question.content}</div>
    ${question.options ? `
      <div class="question-options">
        ${question.options.map((opt, i) => `
          <div class="question-option ${savedAnswer === String.fromCharCode(65 + i) ? 'selected' : ''}"
               onclick="selectOption('${String.fromCharCode(65 + i)}')"
               data-option="${String.fromCharCode(65 + i)}">
            <span class="option-label">${String.fromCharCode(65 + i)}</span>
            <span class="option-text">${opt}</span>
          </div>
        `).join('')}
      </div>
    ` : `
      <div class="answer-input">
        <textarea id="answer-textarea" placeholder="请输入答案"
          onchange="setAnswerText(this.value)">${savedAnswer || ''}</textarea>
      </div>
    `}
  `
}

/**
 * 选择选项
 */
export function selectOption(option) {
  const question = currentQuestions[currentQuestionIndex]
  currentAnswers[question.question_id] = option

  // 更新UI
  document.querySelectorAll('.question-option').forEach(el => {
    el.classList.remove('selected')
  })
  document.querySelector(`[data-option="${option}"]`)?.classList.add('selected')
}

/**
 * 设置文本答案
 */
export function setAnswerText(text) {
  const question = currentQuestions[currentQuestionIndex]
  currentAnswers[question.question_id] = text
}

/**
 * 上一题
 */
export function prevQuestion() {
  if (currentQuestionIndex > 0) {
    currentQuestionIndex--
    renderCurrentQuestion()
  }
}

/**
 * 下一题
 */
export function nextQuestion() {
  if (currentQuestionIndex < currentQuestions.length - 1) {
    // 检查是否已答
    const question = currentQuestions[currentQuestionIndex]
    if (!currentAnswers[question.question_id]) {
      Toast.warning('请先作答')
      return
    }
    currentQuestionIndex++
    renderCurrentQuestion()
  }
}

/**
 * 提交练习
 */
export async function submitPractice() {
  // 检查是否全部作答
  const unanswered = currentQuestions.filter(q => !currentAnswers[q.question_id])
  if (unanswered.length > 0) {
    Toast.warning(`还有 ${unanswered.length} 题未作答`)
    return
  }

  const btn = document.querySelector('.btn-success')
  if (btn) setButtonLoading(btn, true)

  try {
    const result = await practiceService.submitPractice(currentPractice.practice_id, {
      answers: currentQuestions.map(q => ({
        question_id: q.question_id,
        answer: currentAnswers[q.question_id]
      }))
    })

    if (result.success) {
      renderPracticeResult(result.data)
      Toast.success('提交成功')
    } else {
      Toast.error(result.message || '提交失败')
    }
  } catch (error) {
    Toast.error('提交失败：' + error.message)
  } finally {
    if (btn) setButtonLoading(btn, false)
  }
}

/**
 * 渲染练习结果
 */
function renderPracticeResult(result) {
  const container = document.getElementById('practice-container')
  if (!container) return

  container.innerHTML = `
    <div class="result-page">
      <div class="result-header">
        <h2>练习完成</h2>
        <div class="result-score">${result.score || 0}分</div>
      </div>

      <div class="result-summary">
        <div class="summary-item">
          <span class="summary-value">${result.correct_count || 0}</span>
          <span class="summary-label">正确</span>
        </div>
        <div class="summary-item">
          <span class="summary-value">${result.wrong_count || 0}</span>
          <span class="summary-label">错误</span>
        </div>
        <div class="summary-item">
          <span class="summary-value">${result.accuracy || 0}%</span>
          <span class="summary-label">正确率</span>
        </div>
      </div>

      <div class="result-analysis">
        <h3>障碍诊断</h3>
        ${renderBarrierAnalysis(result.barrier_analysis)}
      </div>

      <!-- 学习计划入口 -->
      <div class="learning-plan-entrance" onclick="handleShowLearningPlan()">
        <div class="learning-plan-entrance-header">
          <span class="learning-plan-entrance-title">
            <span class="icon">📖</span>
            个性化学习计划
          </span>
          <span class="learning-plan-entrance-badge">NEW</span>
        </div>
        <p class="learning-plan-entrance-desc">根据您的学习情况，AI已为您生成专属学习计划</p>
        <div class="learning-plan-entrance-meta">
          <span>📅 2周计划</span>
          <span>⏱️ 每天30分钟</span>
        </div>
      </div>

      <div class="result-actions">
        <button class="btn-secondary" onclick="reviewWrongQuestions()">查看错题</button>
        <button class="btn-secondary" onclick="handleShowLearningPlan()">查看计划</button>
        <button class="btn-primary" onclick="loadPracticeTasks()">返回列表</button>
      </div>
    </div>
  `
}

/**
 * 渲染障碍分析
 */
function renderBarrierAnalysis(analysis) {
  if (!analysis) return '<p class="empty">暂无分析数据</p>'

  return `
    <div class="barrier-cards">
      ${analysis.concept > 0 ? `
        <div class="barrier-card concept">
          <span class="barrier-type">概念理解型</span>
          <span class="barrier-count">${analysis.concept}次</span>
        </div>
      ` : ''}
      ${analysis.reading > 0 ? `
        <div class="barrier-card reading">
          <span class="barrier-type">审题障碍型</span>
          <span class="barrier-count">${analysis.reading}次</span>
        </div>
      ` : ''}
      ${analysis.expression > 0 ? `
        <div class="barrier-card expression">
          <span class="barrier-type">表述障碍型</span>
          <span class="barrier-count">${analysis.expression}次</span>
        </div>
      ` : ''}
    </div>
    ${analysis.suggestions ? `
      <div class="suggestions">
        <h4>学习建议</h4>
        <ul>
          ${analysis.suggestions.map(s => `<li>${s}</li>`).join('')}
        </ul>
      </div>
    ` : ''}
  `
}

/**
 * 查看错题
 */
export function reviewWrongQuestions() {
  // TODO: 跳转到错题复习页面
  Toast.info('错题复习功能开发中')
}

/**
 * 显示学习计划（从练习结果页进入）
 */
export async function handleShowLearningPlan() {
  // 先加载学习计划，然后显示弹窗
  try {
    const studentId = getCurrentStudentId()
    if (!studentId) {
      Toast.error('请先登录')
      return
    }

    const result = await diagnosisService.getStudentLearningPlan(studentId)

    if (result.success && result.data) {
      // 设置当前计划并显示弹窗
      showLearningPlanModal()
    } else {
      Toast.info('暂无学习计划，请等待老师生成')
    }
  } catch (error) {
    console.error('加载学习计划失败:', error)
    Toast.info('暂无学习计划，请等待老师生成')
  }
}

/**
 * 加载历史真题
 */
export async function loadHistoricalQuestions() {
  const container = document.getElementById('history-questions-list')
  if (!container) return

  showLoading('加载历史真题...')

  try {
    const result = await practiceService.getHistoricalQuestions()

    if (result.success) {
      renderHistoricalQuestions(result.data.questions || [])
    } else {
      Toast.error('加载失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 渲染历史真题
 */
function renderHistoricalQuestions(questions) {
  const container = document.getElementById('history-questions-list')
  if (!container) return

  if (questions.length === 0) {
    container.innerHTML = '<p class="empty">暂无历史真题</p>'
    return
  }

  container.innerHTML = questions.map(q => `
    <div class="history-question-card">
      <div class="question-type">${q.exam_year} ${q.exam_type}</div>
      <div class="question-content">${q.content}</div>
      <div class="question-footer">
        <span>知识点: ${(q.knowledge_points || []).join(', ')}</span>
      </div>
    </div>
  `).join('')
}

// ==================== 辅助函数 ====================

function getTaskTitle(task) {
  if (task.title) return task.title
  const kps = (task.knowledge_points || []).slice(0, 2).join(', ')
  return `练习任务 - ${kps}`
}

function getStatusText(status) {
  const map = {
    pending: '待完成',
    completed: '已完成',
    overdue: '已过期'
  }
  return map[status] || status
}

function getProgress(task) {
  if (task.status === 'completed') return 100
  if (task.status === 'overdue') return 100
  return task.progress || 0
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.startPractice = startPractice
  window.selectOption = selectOption
  window.setAnswerText = setAnswerText
  window.prevQuestion = prevQuestion
  window.nextQuestion = nextQuestion
  window.submitPractice = submitPractice
  window.reviewWrongQuestions = reviewWrongQuestions
  window.loadPracticeTasks = loadPracticeTasks
  window.loadHistoricalQuestions = loadHistoricalQuestions
}
