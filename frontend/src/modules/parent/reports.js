/**
 * 家长端 - 周报模块
 * 显示子女周报
 */

import { parentService } from '../../services/parent.js'

let currentChildId = null

export async function initParentReports() {
  const container = document.getElementById('reports-content')
  if (!container) return

  // 从URL参数获取student_id
  const urlParams = new URLSearchParams(window.location.hash.split('?')[1] || '')
  currentChildId = urlParams.get('student_id')

  if (!currentChildId) {
    // 获取第一个孩子
    const childrenResult = await parentService.getChildren()
    if (childrenResult.success && childrenResult.children.length > 0) {
      currentChildId = childrenResult.children[0].student_id
    }
  }

  if (currentChildId) {
    await loadWeeklyReport(container, currentChildId)
  } else {
    container.innerHTML = '<div class="empty-state"><p>暂无周报数据</p></div>'
  }
}

async function loadWeeklyReport(container, studentId) {
  showLoading(container)

  try {
    const weeklyResult = await parentService.getChildWeekly(studentId)
    const reportResult = await parentService.getChildReport(studentId)

    if (weeklyResult.success) {
      renderWeeklyReport(container, weeklyResult.weekly, reportResult.report)
    } else {
      container.innerHTML = '<div class="empty-state"><p>加载周报失败</p></div>'
    }
  } catch (error) {
    console.error('加载周报失败:', error)
    container.innerHTML = '<div class="empty-state"><p>加载失败，请重试</p></div>'
  }
}

function renderWeeklyReport(container, weekly, report) {
  const barrierTypeNames = {
    'concept': '概念理解型',
    'reading': '审题障碍型',
    'expression': '表述障碍型'
  }

  const barrierType = typeof weekly.barrier_type === 'string'
    ? weekly.barrier_type
    : (weekly.barrier_type?.dominant || '概念理解型')

  container.innerHTML = `
    <div class="weekly-report">
      <div class="report-header">
        <div class="report-student">
          <div class="avatar-large">${report?.student_name?.charAt(0) || '学'}</div>
          <div>
            <h2>${report?.student_name || '学生'}</h2>
            <p>${report?.grade || ''} · ${report?.class_name || ''}</p>
          </div>
        </div>
        <div class="report-period">
          <span>${weekly.week_start}</span> ~ <span>${weekly.week_end}</span>
        </div>
      </div>

      <div class="report-summary">
        <div class="summary-card">
          <div class="summary-icon teal">
            <svg viewBox="0 0 24 24" stroke-width="2" width="24" height="24"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
          </div>
          <div class="summary-value">${weekly.practice_completed}/${weekly.practice_count}</div>
          <div class="summary-label">本周练习完成</div>
        </div>
        <div class="summary-card">
          <div class="summary-icon amber">
            <svg viewBox="0 0 24 24" stroke-width="2" width="24" height="24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
          </div>
          <div class="summary-value">${weekly.accuracy_rate ? Math.round(weekly.accuracy_rate * 100) : '--'}%</div>
          <div class="summary-label">正确率</div>
        </div>
        <div class="summary-card">
          <div class="summary-icon purple">
            <svg viewBox="0 0 24 24" stroke-width="2" width="24" height="24"><path d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"/><path d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z"/></svg>
          </div>
          <div class="summary-value">${weekly.streak_days || 0}</div>
          <div class="summary-label">连续学习天数</div>
        </div>
      </div>

      <div class="report-section">
        <h3 class="section-title">薄弱知识点</h3>
        <div class="knowledge-chips">
          ${(weekly.weak_knowledge_points || []).map(kp => `
            <span class="knowledge-chip">${kp}</span>
          `).join('')}
          ${(!weekly.weak_knowledge_points || weekly.weak_knowledge_points.length === 0) ? '<span class="text-muted">暂无薄弱知识点</span>' : ''}
        </div>
      </div>

      <div class="report-section">
        <h3 class="section-title">障碍类型分析</h3>
        <div class="barrier-info">
          <span class="barrier-badge ${barrierType}">${barrierTypeNames[barrierType] || barrierType}</span>
          <p class="barrier-hint">了解孩子的学习障碍类型，有助于针对性辅导</p>
        </div>
      </div>

      <div class="report-section">
        <h3 class="section-title">教师建议</h3>
        <div class="advice-card">
          <p>建议加强基础概念复习，使用思维导图梳理知识体系，重点理解"为什么"而非死记硬背。</p>
          <p class="text-muted" style="margin-top: 8px;">— 智辅化学 AI 诊断</p>
        </div>
      </div>
    </div>
  `
}

function showLoading(container) {
  container.innerHTML = '<div class="loading-state"><p>加载中...</p></div>'
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.parentModule = window.parentModule || {}
  window.parentModule.initParentReports = initParentReports
}
