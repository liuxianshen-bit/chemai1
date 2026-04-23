/**
 * 学生端 - 错题本模块
 */
import { practiceService } from '../../services/index.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

// 全局状态
let currentWrongList = []

/**
 * 初始化错题本模块
 */
export async function initWrongModule() {
  const container = document.getElementById('wrong-container')
  if (!container) return

  await loadWrongQuestions()
}

/**
 * 加载错题列表
 */
export async function loadWrongQuestions() {
  const container = document.getElementById('wrong-list')
  if (!container) return

  showLoading('加载错题本...')

  try {
    const result = await practiceService.getWrongQuestions()

    if (result.success) {
      currentWrongList = result.data.questions || []
      renderWrongList(currentWrongList)
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
 * 渲染错题列表
 */
function renderWrongList(questions) {
  const container = document.getElementById('wrong-list')
  if (!container) return

  if (questions.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-size:3rem;margin-bottom:16px;">🎉</div>
        <p>太棒了！暂无错题</p>
      </div>
    `
    return
  }

  // 按知识点分组
  const grouped = groupByKnowledgePoint(questions)

  container.innerHTML = Object.entries(grouped).map(([kp, qs]) => `
    <div class="wrong-group">
      <div class="wrong-group-header">
        <h3>${kp}</h3>
        <span class="badge">${qs.length}题</span>
      </div>
      <div class="wrong-group-list">
        ${qs.map(q => renderWrongItem(q)).join('')}
      </div>
    </div>
  `).join('')
}

/**
 * 渲染错题项
 */
function renderWrongItem(question) {
  return `
    <div class="wrong-question-card" onclick="showWrongDetail('${question.id}')">
      <div class="wrong-question-header">
        <span class="question-type">${question.type_name || '选择题'}</span>
        <span class="wrong-time">错误次数: ${question.wrong_count || 1}</span>
      </div>
      <div class="wrong-question-content">${question.content}</div>
      <div class="wrong-answer-row">
        <span class="wrong-answer">✗ ${question.wrong_answer}</span>
        <span class="correct-answer">✓ ${question.correct_answer}</span>
      </div>
      ${question.status === 'mastered' ? '<span class="status done">已掌握</span>' : ''}
    </div>
  `
}

/**
 * 按知识点分组
 */
function groupByKnowledgePoint(questions) {
  return questions.reduce((acc, q) => {
    const kps = q.knowledge_points || ['未分类']
    kps.forEach(kp => {
      if (!acc[kp]) acc[kp] = []
      acc[kp].push(q)
    })
    return acc
  }, {})
}

/**
 * 查看错题详情
 */
export async function showWrongDetail(questionId) {
  const question = currentWrongList.find(q => q.id === questionId)
  if (!question) return

  const modal = document.getElementById('wrong-detail-modal')
  if (!modal) return

  const content = document.getElementById('wrong-detail-content')
  if (content) {
    content.innerHTML = `
      <div class="detail-header">
        <span class="question-type">${question.type_name || '选择题'}</span>
        <span class="wrong-count">错误 ${question.wrong_count || 1} 次</span>
      </div>

      <div class="detail-section">
        <h4>题目内容</h4>
        <p class="question-content">${question.content}</p>
      </div>

      ${question.options ? `
        <div class="detail-section">
          <h4>选项</h4>
          <div class="options-list">
            ${question.options.map((opt, i) => `
              <div class="option-item ${opt === question.correct_answer ? 'correct' : ''} ${opt === question.wrong_answer ? 'wrong' : ''}">
                ${String.fromCharCode(65 + i)}. ${opt}
                ${opt === question.correct_answer ? ' ✓' : ''}
                ${opt === question.wrong_answer ? ' ✗' : ''}
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}

      <div class="detail-section">
        <h4>你的答案</h4>
        <p class="wrong-answer-text">${question.wrong_answer || '未作答'}</p>
      </div>

      <div class="detail-section">
        <h4>正确答案</h4>
        <p class="correct-answer-text">${question.correct_answer}</p>
      </div>

      ${question.explanation ? `
        <div class="detail-section">
          <h4>解析</h4>
          <p class="explanation">${question.explanation}</p>
        </div>
      ` : ''}

      ${question.barrier_type ? `
        <div class="detail-section">
          <h4>障碍类型</h4>
          <span class="barrier-tag ${question.barrier_type}">${getBarrierName(question.barrier_type)}</span>
        </div>
      ` : ''}

      <div class="detail-actions">
        <button class="btn-secondary" onclick="markAsMastered('${questionId}')">
          ${question.status === 'mastered' ? '取消掌握' : '标记为已掌握'}
        </button>
        <button class="btn-primary" onclick="doPracticeAgain('${questionId}')">再次练习</button>
      </div>
    `
  }

  modal.style.display = 'flex'
}

/**
 * 标记为已掌握
 */
export async function markAsMastered(questionId) {
  showLoading()

  try {
    const result = await practiceService.markAsMastered(questionId)

    if (result.success) {
      Toast.success('已更新')
      await loadWrongQuestions()
      closeWrongModal()
    } else {
      Toast.error('操作失败')
    }
  } catch (error) {
    Toast.error('操作失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 再次练习
 */
export function doPracticeAgain(questionId) {
  // TODO: 跳转到针对这道题的练习
  Toast.info('功能开发中')
  closeWrongModal()
}

/**
 * 关闭弹窗
 */
export function closeWrongModal() {
  const modal = document.getElementById('wrong-detail-modal')
  if (modal) modal.style.display = 'none'
}

/**
 * 获取障碍类型名称
 */
function getBarrierName(type) {
  const names = {
    concept: '概念理解型',
    reading: '审题障碍型',
    expression: '表述障碍型'
  }
  return names[type] || type
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.showWrongDetail = showWrongDetail
  window.markAsMastered = markAsMastered
  window.doPracticeAgain = doPracticeAgain
  window.closeWrongModal = closeWrongModal
}
