/**
 * 学生端 - 学习计划模块
 */
import { diagnosisService } from '../../services/index.js'
import { Toast, showLoading, hideLoading, callAgentApi } from '../../components/index.js'

// 全局状态
let currentPlan = null
let completedTasks = new Set()

/**
 * 初始化学习计划模块
 */
export async function initLearningPlanModule() {
  const container = document.getElementById('learning-plan-container')
  if (!container) return

  await loadStudentLearningPlan()
}

/**
 * 加载学生学习计划
 */
export async function loadStudentLearningPlan() {
  const studentId = getCurrentStudentId()
  if (!studentId) return

  showLoading('加载学习计划...')

  try {
    const result = await diagnosisService.getStudentLearningPlan(studentId)

    if (result.success && result.data) {
      currentPlan = result.data
      renderLearningPlan(result.data)
    } else {
      showNoPlanMessage()
    }
  } catch (error) {
    console.error('加载学习计划失败:', error)
    showNoPlanMessage()
  } finally {
    hideLoading()
  }
}

/**
 * 渲染学习计划
 */
function renderLearningPlan(data) {
  const container = document.getElementById('learning-plan-container')
  if (!container) return

  const plan = data.plan || data

  container.innerHTML = `
    <div class="learning-plan-page">
      <!-- 计划头部 -->
      <div class="plan-header">
        <h2 class="plan-title">${plan.plan_title || '个性化学习计划'}</h2>
        <span class="plan-period">${plan.plan_period || ''}</span>
      </div>

      <!-- 障碍干预提示 -->
      ${plan['barrier针对性的干预'] ? `
        <div class="barrier-intervention">
          <h3>针对您的障碍类型</h3>
          ${plan['barrier针对性的干预'].map(item => `
            <div class="intervention-card ${item.barrier}">
              <div class="intervention-header">
                <span class="barrier-tag ${getBarrierClass(item.barrier)}">${item.barrier}</span>
              </div>
              <div class="intervention-content">
                <p><strong>策略：</strong>${item.strategy}</p>
                <p><strong>练习建议：</strong>${item.practise_tips}</p>
              </div>
            </div>
          `).join('')}
        </div>
      ` : ''}

      <!-- 每日任务 -->
      <section class="plan-section">
        <h3 class="section-title">每日任务</h3>
        <div class="daily-tasks">
          ${renderDailyTasks(plan.daily_tasks)}
        </div>
      </section>

      <!-- 周目标 -->
      ${plan.weekly_goals ? `
        <section class="plan-section">
          <h3 class="section-title">周目标</h3>
          <div class="weekly-goals">
            ${plan.weekly_goals.map(week => `
              <div class="week-card">
                <div class="week-header">${week.week}</div>
                <ul class="week-goals-list">
                  ${week.goals.map(g => `<li>${g}</li>`).join('')}
                </ul>
                ${week.milestone ? `<div class="milestone">🎯 ${week.milestone}</div>` : ''}
              </div>
            `).join('')}
          </div>
        </section>
      ` : ''}

      <!-- 激励语 -->
      ${plan.motivation_tips ? `
        <div class="motivation-tips">
          ${plan.motivation_tips.map(tip => `<p>💪 ${tip}</p>`).join('')}
        </div>
      ` : ''}

      <!-- 家长沟通建议 -->
      ${plan.parent_communication_suggestion ? `
        <div class="parent-suggestion">
          <h4>给家长的建议</h4>
          <p>${plan.parent_communication_suggestion}</p>
        </div>
      ` : ''}
    </div>
  `
}

/**
 * 渲染每日任务
 */
function renderDailyTasks(dailyTasks) {
  if (!dailyTasks || dailyTasks.length === 0) {
    return '<p class="empty">暂无任务安排</p>'
  }

  return dailyTasks.map((task, index) => {
    const taskId = `task-${index}`
    const isCompleted = completedTasks.has(taskId)

    return `
      <div class="daily-task-card ${isCompleted ? 'completed' : ''}">
        <div class="task-checkbox" onclick="toggleTaskComplete('${taskId}', ${index})">
          ${isCompleted ? '✓' : '○'}
        </div>
        <div class="task-content">
          <div class="task-header">
            <span class="task-day">${task.day}</span>
            <span class="task-duration">${task.duration || ''}</span>
          </div>
          <div class="task-text">${task.content}</div>
          ${task.resource_type ? `
            <span class="task-resource">📚 ${task.resource_type}</span>
          ` : ''}
        </div>
      </div>
    `
  }).join('')
}

/**
 * 切换任务完成状态
 */
export function toggleTaskComplete(taskId, index) {
  if (completedTasks.has(taskId)) {
    completedTasks.delete(taskId)
  } else {
    completedTasks.add(taskId)
  }

  // 更新UI
  const taskCard = document.querySelector(`[data-task-id="${taskId}"]`)
  if (taskCard) {
    taskCard.classList.toggle('completed')
  }

  // 重新渲染任务列表（保持状态）
  if (currentPlan && currentPlan.plan && currentPlan.plan.daily_tasks) {
    const tasksContainer = document.querySelector('.daily-tasks')
    if (tasksContainer) {
      tasksContainer.innerHTML = renderDailyTasks(currentPlan.plan.daily_tasks)
    }
  }

  // 提示
  Toast.success(completedTasks.has(taskId) ? '任务完成！' : '任务已取消')
}

/**
 * 获取障碍样式类
 */
function getBarrierClass(barrier) {
  if (barrier.includes('概念')) return 'concept'
  if (barrier.includes('审题')) return 'reading'
  if (barrier.includes('表述')) return 'expression'
  return ''
}

/**
 * 显示无学习计划
 */
function showNoPlanMessage() {
  const container = document.getElementById('learning-plan-container')
  if (!container) return

  container.innerHTML = `
    <div class="empty-state">
      <div style="font-size:3rem;margin-bottom:16px;">📖</div>
      <p>暂无学习计划</p>
      <p class="text-muted">完成练习后，老师会为您生成个性化学习计划</p>
    </div>
  `
}

/**
 * 显示学习计划弹窗（从练习结果页进入）
 */
export function showLearningPlanModal() {
  const modal = document.getElementById('learning-plan-modal')
  if (!modal) return

  const content = document.getElementById('learning-plan-modal-content')
  if (!content) return

  if (!currentPlan) {
    content.innerHTML = `
      <div class="empty-state">
        <p>正在加载学习计划...</p>
      </div>
    `
    // 加载学习计划
    loadStudentLearningPlanForModal()
    return
  }

  renderModalContent(content, currentPlan)
  modal.style.display = 'flex'
}

/**
 * 加载学习计划到弹窗
 */
async function loadStudentLearningPlanForModal() {
  const studentId = getCurrentStudentId()
  if (!studentId) return

  try {
    const result = await diagnosisService.getStudentLearningPlan(studentId)

    const content = document.getElementById('learning-plan-modal-content')
    if (!content) return

    if (result.success && result.data) {
      currentPlan = result.data
      renderModalContent(content, result.data)
    } else {
      content.innerHTML = `
        <div class="empty-state">
          <div style="font-size:3rem;margin-bottom:16px;">📖</div>
          <p>暂无学习计划</p>
          <p class="text-muted">完成练习后，老师会为您生成个性化学习计划</p>
        </div>
      `
    }
  } catch (error) {
    console.error('加载学习计划失败:', error)
  }
}

/**
 * 渲染弹窗内容
 */
function renderModalContent(content, data) {
  const plan = data.plan || data

  content.innerHTML = `
    <div class="plan-summary">
      <h3>${plan.plan_title || '个性化学习计划'}</h3>
      <p class="plan-period">计划周期：${plan.plan_period || '未知'}</p>
    </div>

    <div class="plan-quick-view">
      <div class="quick-item">
        <span class="quick-icon">📅</span>
        <span class="quick-value">${(plan.daily_tasks || []).length}天</span>
        <span class="quick-label">学习天数</span>
      </div>
      <div class="quick-item">
        <span class="quick-icon">⏱️</span>
        <span class="quick-value">${plan.daily_tasks?.[0]?.duration || '30分钟'}</span>
        <span class="quick-label">每天时长</span>
      </div>
      <div class="quick-item">
        <span class="quick-icon">🎯</span>
        <span class="quick-value">${(plan.weekly_goals || []).length}个</span>
        <span class="quick-label">周目标</span>
      </div>
    </div>

    <div class="plan-actions">
      <button class="btn-primary" onclick="viewFullLearningPlan()">查看完整计划</button>
      <button class="btn-secondary" onclick="closeLearningPlanModal()">关闭</button>
    </div>
  `
}

/**
 * 查看完整学习计划
 */
export function viewFullLearningPlan() {
  closeLearningPlanModal()

  // 切换到学习计划Tab
  const tabBtn = document.querySelector('.tab-btn[data-tab="learning-plan"]')
  if (tabBtn) {
    tabBtn.click()
  }

  // 或者直接跳转到学习计划页面
  initLearningPlanModule()
}

/**
 * 关闭学习计划弹窗
 */
export function closeLearningPlanModal() {
  const modal = document.getElementById('learning-plan-modal')
  if (modal) modal.style.display = 'none'
}

/**
 * 获取当前学生ID
 */
function getCurrentStudentId() {
  try {
    const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
    return user.id
  } catch {
    return null
  }
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.toggleTaskComplete = toggleTaskComplete
  window.showLearningPlanModal = showLearningPlanModal
  window.viewFullLearningPlan = viewFullLearningPlan
  window.closeLearningPlanModal = closeLearningPlanModal
}
