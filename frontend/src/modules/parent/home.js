/**
 * 家长端 - 首页模块
 * 显示子女学习概况
 */

import { parentService } from '../../services/parent.js'

let currentChildren = []

export async function initParentHome() {
  const container = document.getElementById('home-content')
  if (!container) return

  showLoading(container)
  try {
    const result = await parentService.getChildren()
    if (result.success && result.children.length > 0) {
      currentChildren = result.children
      renderChildrenOverview(container, result.children)
    } else {
      renderEmptyState(container)
    }
  } catch (error) {
    console.error('加载子女信息失败:', error)
    container.innerHTML = '<div class="empty-state"><p>加载失败，请重试</p></div>'
  }
}

function renderChildrenOverview(container, children) {
  let html = '<div class="children-overview">'

  children.forEach(child => {
    html += `
      <div class="child-card" onclick="parentModule.showChildDetail('${child.student_id}')">
        <div class="child-header">
          <div class="child-avatar">${child.student_name.charAt(0)}</div>
          <div class="child-info">
            <h3>${child.student_name}</h3>
            <p>${child.grade} · ${child.class_name}</p>
          </div>
          <div class="child-relation">${child.relation}</div>
        </div>
        <div class="child-stats" id="child-stats-${child.student_id}">
          <div class="stat-item">
            <div class="stat-value">--</div>
            <div class="stat-label">本周练习</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">--</div>
            <div class="stat-label">正确率</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">--</div>
            <div class="stat-label">连续天数</div>
          </div>
        </div>
      </div>
    `
  })

  html += '</div>'

  // 如果有绑定码，显示绑定提示
  html += `
    <div class="bind-hint" onclick="parentModule.showBindModal()">
      <svg viewBox="0 0 24 24" stroke-width="2" width="20" height="20"><path d="M12 5v14M5 12h14"/></svg>
      <span>绑定更多子女</span>
    </div>
  `

  container.innerHTML = html

  // 加载每个子女的详细数据
  children.forEach(child => {
    loadChildStats(child.student_id)
  })
}

async function loadChildStats(studentId) {
  try {
    const result = await parentService.getChildReport(studentId)
    const weeklyResult = await parentService.getChildWeekly(studentId)

    const statsContainer = document.getElementById(`child-stats-${studentId}`)
    if (statsContainer && result.success) {
      const report = result.report
      const weekly = weeklyResult.weekly || {}

      statsContainer.innerHTML = `
        <div class="stat-item">
          <div class="stat-value">${weekly.practice_completed || 0}/${weekly.practice_count || 0}</div>
          <div class="stat-label">本周练习</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">${weekly.accuracy_rate ? Math.round(weekly.accuracy_rate * 100) : '--'}%</div>
          <div class="stat-label">正确率</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">${weekly.streak_days || report.exercises_completed || 0}</div>
          <div class="stat-label">连续天数</div>
        </div>
      `
    }
  } catch (error) {
    console.error('加载子女统计数据失败:', error)
  }
}

function renderEmptyState(container) {
  container.innerHTML = `
    <div class="empty-state">
      <div class="empty-state-icon">👨‍👩‍👧</div>
      <h3>暂无绑定子女</h3>
      <p>请使用绑定码绑定您的孩子</p>
      <button class="btn-primary" onclick="parentModule.showBindModal()">立即绑定</button>
    </div>
  `
}

function showLoading(container) {
  container.innerHTML = '<div class="loading-state"><p>加载中...</p></div>'
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.parentModule = window.parentModule || {}
  window.parentModule.initParentHome = initParentHome
  window.parentModule.showChildDetail = showChildDetail
  window.parentModule.showBindModal = showBindModal
}

export function showChildDetail(studentId) {
  const child = currentChildren.find(c => c.student_id === studentId)
  if (!child) return

  // 跳转到周报页面
  window.location.href = `#reports?student_id=${studentId}`
}

export function showBindModal() {
  const modal = document.getElementById('bind-modal')
  if (modal) {
    modal.classList.add('active')
  }
}
