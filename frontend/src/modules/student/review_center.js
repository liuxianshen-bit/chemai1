/**
 * 学生端 - 复习中心模块
 */

import { reviewService } from '../../services/practice.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

let dueTasks = []
let historyTasks = []
let currentTab = 'today' // today, history

/**
 * 初始化复习中心模块
 */
export async function initReviewCenterModule() {
  const container = document.getElementById('review-center-container')
  if (!container) return

  showLoading('加载复习任务...')

  try {
    await loadData()
    render(container)
  } catch (e) {
    console.error('初始化复习中心失败', e)
    Toast.error('加载失败')
  } finally {
    hideLoading()
  }
}

/**
 * 加载数据
 */
async function loadData() {
  const studentId = getCurrentStudentId()
  if (!studentId) return

  const [dueRes, historyRes] = await Promise.all([
    reviewService.getDueReviews(studentId),
    reviewService.getReviewHistory(studentId, 20)
  ])

  if (dueRes.success) {
    dueTasks = dueRes.tasks || []
  }

  if (historyRes.success) {
    historyTasks = historyRes.history || []
  }
}

/**
 * 获取当前学生ID
 */
function getCurrentStudentId() {
  try {
    const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
    return user.student_id || user.id
  } catch {
    return null
  }
}

/**
 * 渲染复习中心
 */
function render(container) {
  const totalDue = dueTasks.length
  const todayCompleted = historyTasks.filter(t => isToday(t.completed_at)).length

  container.innerHTML = `
    <!-- 统计卡片 -->
    <div class="stats-row" style="margin-bottom: 24px;">
      <div class="stat-card teal">
        <div class="stat-label">今日待复习</div>
        <div class="stat-value">${totalDue}</div>
      </div>
      <div class="stat-card amber">
        <div class="stat-label">今日已完成</div>
        <div class="stat-value">${todayCompleted}</div>
      </div>
      <div class="stat-card purple">
        <div class="stat-label">连续复习</div>
        <div class="stat-value">${calculateStreak()}</div>
      </div>
    </div>

    <!-- 标签切换 -->
    <div class="filter-bar" style="display: flex; gap: 8px; margin-bottom: 16px;">
      <button class="filter-btn ${currentTab === 'today' ? 'active' : ''}"
              onclick="reviewCenterModule.switchTab('today')"
              style="padding: 8px 16px; border: none; border-radius: 20px; font-size: 0.8125rem; cursor: pointer;
                     ${currentTab === 'today' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
        📅 今日复习 (${totalDue})
      </button>
      <button class="filter-btn ${currentTab === 'history' ? 'active' : ''}"
              onclick="reviewCenterModule.switchTab('history')"
              style="padding: 8px 16px; border: none; border-radius: 20px; font-size: 0.8125rem; cursor: pointer;
                     ${currentTab === 'history' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
        📊 历史记录
      </button>
    </div>

    <!-- 艾宾浩斯说明 -->
    <div class="panel" style="margin-bottom: 16px;">
      <div class="panel-body" style="display: flex; align-items: center; gap: 16px; padding: 12px 16px;">
        <div style="font-size: 1.5rem;">🧠</div>
        <div style="flex: 1;">
          <div style="font-size: 0.875rem; font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">艾宾浩斯间隔复习</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">根据遗忘曲线，在最佳时机提醒复习，达到长期记忆效果</div>
        </div>
        <div style="text-align: center;">
          <div style="font-size: 1.25rem; font-weight: 700; color: var(--accent);">${calculateMasteryRate()}%</div>
          <div style="font-size: 0.625rem; color: var(--text-muted);">掌握率</div>
        </div>
      </div>
    </div>

    <!-- 任务列表 -->
    <div id="review-tasks-list">
      ${currentTab === 'today' ? renderTodayTasks() : renderHistoryTasks()}
    </div>
  `
}

/**
 * 渲染今日任务
 */
function renderTodayTasks() {
  if (dueTasks.length === 0) {
    return `
      <div class="panel">
        <div class="panel-body" style="padding: 48px; text-align: center;">
          <div style="font-size: 3rem; margin-bottom: 16px;">🎉</div>
          <p style="color: var(--text-muted); font-size: 0.875rem;">太棒了！今日复习任务已全部完成</p>
          <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 8px;">保持学习势头，明天继续加油！</p>
        </div>
      </div>
    `
  }

  return `
    <div class="review-tasks">
      ${dueTasks.map(task => `
        <div class="panel" style="margin-bottom: 12px;">
          <div class="panel-body">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
              <div>
                <span class="barrier-tag" style="background: var(--amber-bg); color: var(--amber); margin-right: 8px;">
                  ${getLevelName(task.review_level)}
                </span>
                <span style="font-size: 0.75rem; color: var(--text-muted);">
                  ${task.knowledge_points?.join(', ') || '知识点'}
                </span>
              </div>
              <span style="font-size: 0.75rem; color: var(--text-muted);">
                ${task.difficulty === 'easy' ? '简单' : task.difficulty === 'medium' ? '中等' : '困难'}
              </span>
            </div>

            <div style="font-size: 0.9375rem; color: var(--text-primary); margin-bottom: 12px; line-height: 1.5;">
              ${task.content || '题目内容加载中...'}
            </div>

            ${task.options ? `
              <div style="margin-bottom: 12px;">
                ${task.options.map((opt, i) => `
                  <div style="padding: 8px 12px; background: var(--bg-tertiary); border-radius: 6px; margin-bottom: 4px; font-size: 0.875rem;">
                    ${String.fromCharCode(65 + i)}. ${opt}
                  </div>
                `).join('')}
              </div>
            ` : ''}

            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <button class="btn-primary btn-sm" onclick="reviewCenterModule.showAnswer('${task.task_id}')"
                      style="padding: 6px 12px; font-size: 0.8125rem; border-radius: 6px;">
                查看答案
              </button>
              <button class="btn-secondary btn-sm" onclick="reviewCenterModule.markCorrect('${task.task_id}')"
                      style="padding: 6px 12px; font-size: 0.8125rem; border-radius: 6px;">
                ✓ 掌握了
              </button>
              <button class="btn-secondary btn-sm" onclick="reviewCenterModule.markWrong('${task.task_id}')"
                      style="padding: 6px 12px; font-size: 0.8125rem; border-radius: 6px;">
                ✗ 还需复习
              </button>
            </div>

            <!-- 答案区域（默认隐藏） -->
            <div id="answer-${task.task_id}" style="display: none; margin-top: 12px; padding: 12px; background: var(--success); border-radius: 8px;">
              <div style="font-size: 0.75rem; color: white; margin-bottom: 4px;">正确答案</div>
              <div style="font-size: 1rem; color: white; font-weight: 600;">${task.answer || '暂无答案'}</div>
              ${task.analysis ? `
                <div style="margin-top: 8px; font-size: 0.8125rem; color: rgba(255,255,255,0.9);">${task.analysis}</div>
              ` : ''}
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `
}

/**
 * 渲染历史记录
 */
function renderHistoryTasks() {
  if (historyTasks.length === 0) {
    return `
      <div class="panel">
        <div class="panel-body" style="padding: 48px; text-align: center;">
          <div style="font-size: 3rem; margin-bottom: 16px;">📚</div>
          <p style="color: var(--text-muted); font-size: 0.875rem;">暂无复习历史</p>
          <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 8px;">开始今日复习，积累学习记录</p>
        </div>
      </div>
    `
  }

  return `
    <div class="review-history">
      ${historyTasks.map(task => `
        <div class="panel" style="margin-bottom: 8px;">
          <div class="panel-body" style="display: flex; align-items: center; gap: 12px; padding: 12px 16px;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: ${task.status === 'mastered' ? 'var(--success)' : 'var(--amber)'}; color: white; display: flex; align-items: center; justify-content: center; font-size: 0.875rem;">
              ${task.status === 'mastered' ? '✓' : '◐'}
            </div>
            <div style="flex: 1; min-width: 0;">
              <div style="font-size: 0.875rem; color: var(--text-primary); margin-bottom: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                ${task.content}
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">
                ${getLevelName(task.review_level)} · ${formatTime(task.completed_at)}
              </div>
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `
}

/**
 * 获取等级名称
 */
function getLevelName(level) {
  const names = {
    0: '初次学习',
    1: '第1次复习',
    2: '第2次复习',
    3: '第3次复习',
    4: '第4次复习',
    5: '已掌握'
  }
  return names[level] || `等级${level}`
}

/**
 * 判断是否是今天
 */
function isToday(dateStr) {
  if (!dateStr) return false
  const date = new Date(dateStr)
  const today = new Date()
  return date.toDateString() === today.toDateString()
}

/**
 * 格式化时间
 */
function formatTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / 86400000)

  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

/**
 * 计算连续复习天数
 */
function calculateStreak() {
  if (historyTasks.length === 0) return 0

  let streak = 0
  let checkDate = new Date()
  checkDate.setHours(0, 0, 0, 0)

  const sortedHistory = [...historyTasks].sort((a, b) =>
    new Date(b.completed_at) - new Date(a.completed_at)
  )

  for (const task of sortedHistory) {
    if (!task.completed_at) continue
    const taskDate = new Date(task.completed_at)
    taskDate.setHours(0, 0, 0, 0)

    const diffDays = Math.floor((checkDate - taskDate) / 86400000)

    if (diffDays === 0 || diffDays === 1) {
      streak++
      checkDate = taskDate
    } else {
      break
    }
  }

  return streak
}

/**
 * 计算掌握率
 */
function calculateMasteryRate() {
  if (historyTasks.length === 0) return 0
  const mastered = historyTasks.filter(t => t.status === 'mastered').length
  return Math.round((mastered / historyTasks.length) * 100)
}

/**
 * 切换标签
 */
export function switchTab(tab) {
  currentTab = tab
  const container = document.getElementById('review-center-container')
  if (container) {
    const tasksList = document.getElementById('review-tasks-list')
    if (tasksList) {
      tasksList.innerHTML = tab === 'today' ? renderTodayTasks() : renderHistoryTasks()
    }
    // 更新tab样式
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.remove('active')
      if ((tab === 'today' && btn.textContent.includes('今日')) ||
          (tab === 'history' && btn.textContent.includes('历史'))) {
        btn.classList.add('active')
        btn.style.background = tab === 'today' ? 'var(--accent)' : 'var(--accent)'
        btn.style.color = 'white'
      } else {
        btn.style.background = 'var(--bg-tertiary)'
        btn.style.color = 'var(--text-secondary)'
      }
    })
  }
}

/**
 * 显示答案
 */
export function showAnswer(taskId) {
  const answerDiv = document.getElementById(`answer-${taskId}`)
  if (answerDiv) {
    answerDiv.style.display = answerDiv.style.display === 'none' ? 'block' : 'none'
  }
}

/**
 * 标记掌握了
 */
export async function markCorrect(taskId) {
  try {
    const result = await reviewService.submitReview(taskId, true)
    if (result.success) {
      Toast.success(result.message || '太棒了！已掌握此知识点')
      await loadData()
      const container = document.getElementById('review-center-container')
      if (container) render(container)
    } else {
      Toast.error('提交失败')
    }
  } catch (e) {
    Toast.error('提交失败：' + e.message)
  }
}

/**
 * 标记还需复习
 */
export async function markWrong(taskId) {
  try {
    const result = await reviewService.submitReview(taskId, false)
    if (result.success) {
      Toast.info(result.message || '已记录，下次还会复习')
      await loadData()
      const container = document.getElementById('review-center-container')
      if (container) render(container)
    } else {
      Toast.error('提交失败')
    }
  } catch (e) {
    Toast.error('提交失败：' + e.message)
  }
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.reviewCenterModule = {
    init: initReviewCenterModule,
    switchTab,
    showAnswer,
    markCorrect,
    markWrong
  }
}

export default {
  init: initReviewCenterModule,
  switchTab,
  showAnswer,
  markCorrect,
  markWrong
}
