/**
 * 学生端 - 报告模块
 */
import { reportService } from '../../services/index.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

// 全局状态
let currentReport = null

/**
 * 初始化学生报告模块
 */
export async function initReportModule() {
  const container = document.getElementById('report-container')
  if (!container) return

  await loadStudentReport()
}

/**
 * 加载学生报告
 */
export async function loadStudentReport() {
  const studentId = getCurrentStudentId()
  if (!studentId) {
    showNoStudentMessage()
    return
  }

  showLoading('加载报告...')

  try {
    const result = await reportService.getStudentReport(studentId)

    if (result.success) {
      currentReport = result.data
      renderStudentReport(result.data)
    } else {
      Toast.error('加载报告失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 渲染学生报告
 */
function renderStudentReport(data) {
  const container = document.getElementById('report-container')
  if (!container) return

  container.innerHTML = `
    <div class="report-page">
      <!-- 概览卡片 -->
      <div class="report-overview">
        <div class="overview-card main">
          <div class="overview-score">${((data.accuracy || 0) * 100).toFixed(0)}%</div>
          <div class="overview-label">总体正确率</div>
        </div>
        <div class="overview-stats">
          <div class="stat-item">
            <span class="stat-value">${data.total_questions || 0}</span>
            <span class="stat-label">完成题目</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">${data.correct_count || 0}</span>
            <span class="stat-label">正确</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">${data.wrong_count || 0}</span>
            <span class="stat-label">错误</span>
          </div>
        </div>
      </div>

      <!-- 知识点掌握 -->
      <section class="report-section">
        <h3 class="section-title">知识点掌握</h3>
        <div class="kp-mastery-list">
          ${renderKPMastery(data.knowledge_mastery || [])}
        </div>
      </section>

      <!-- 障碍分析 -->
      <section class="report-section">
        <h3 class="section-title">障碍类型分析</h3>
        <div class="barrier-analysis">
          ${renderBarrierAnalysis(data.barrier_analysis)}
        </div>
      </section>

      <!-- 学习趋势 -->
      <section class="report-section">
        <h3 class="section-title">学习趋势</h3>
        <div class="trend-chart" id="trend-chart">
          ${renderTrendChart(data.trend)}
        </div>
      </section>

      <!-- 最近练习 -->
      <section class="report-section">
        <h3 class="section-title">最近练习</h3>
        <div class="recent-practice">
          ${renderRecentPractice(data.recent_practices || [])}
        </div>
      </section>
    </div>
  `
}

/**
 * 渲染知识点掌握情况
 */
function renderKPMastery(kpList) {
  if (kpList.length === 0) {
    return '<p class="empty">暂无知识点数据</p>'
  }

  return kpList.map(kp => `
    <div class="kp-item">
      <div class="kp-header">
        <span class="kp-name">${kp.name}</span>
        <span class="kp-percent">${((kp.mastery || 0) * 100).toFixed(0)}%</span>
      </div>
      <div class="kp-bar">
        <div class="kp-fill" style="width: ${((kp.mastery || 0) * 100)}%"></div>
      </div>
    </div>
  `).join('')
}

/**
 * 渲染障碍分析
 */
function renderBarrierAnalysis(analysis) {
  if (!analysis) {
    return '<p class="empty">暂无障碍数据</p>'
  }

  const total = (analysis.concept || 0) + (analysis.reading || 0) + (analysis.expression || 0)

  return `
    <div class="barrier-chart">
      <div class="barrier-bars">
        <div class="barrier-bar-item">
          <div class="barrier-bar concept" style="height: ${total > 0 ? ((analysis.concept || 0) / total * 100) : 0}%"></div>
          <span class="barrier-value">${analysis.concept || 0}</span>
          <span class="barrier-label">概念理解</span>
        </div>
        <div class="barrier-bar-item">
          <div class="barrier-bar reading" style="height: ${total > 0 ? ((analysis.reading || 0) / total * 100) : 0}%"></div>
          <span class="barrier-value">${analysis.reading || 0}</span>
          <span class="barrier-label">审题障碍</span>
        </div>
        <div class="barrier-bar-item">
          <div class="barrier-bar expression" style="height: ${total > 0 ? ((analysis.expression || 0) / total * 100) : 0}%"></div>
          <span class="barrier-value">${analysis.expression || 0}</span>
          <span class="barrier-label">表述障碍</span>
        </div>
      </div>
    </div>
    <div class="barrier-summary">
      ${analysis.suggestions ? `
        <div class="suggestions-box">
          <h4>学习建议</h4>
          <ul>
            ${(analysis.suggestions || []).map(s => `<li>${s}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    </div>
  `
}

/**
 * 渲染趋势图
 */
function renderTrendChart(trend) {
  if (!trend || trend.length === 0) {
    return '<p class="empty">暂无趋势数据</p>'
  }

  const maxScore = 100
  const points = trend.map((v, i) => {
    const x = (i / (trend.length - 1)) * 200
    const y = 100 - v
    return `${x},${y}`
  }).join(' ')

  return `
    <svg class="trend-svg" viewBox="0 0 200 100" preserveAspectRatio="none">
      <defs>
        <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--accent-cyan)" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="var(--accent-cyan)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <polyline
        fill="none"
        stroke="var(--accent-cyan)"
        stroke-width="2"
        points="${points}"
      />
      <polygon
        fill="url(#trendGradient)"
        points="0,100 ${points} 200,100"
      />
    </svg>
    <div class="trend-labels">
      ${trend.map((v, i) => `<span>${formatTrendDate(trend.dates?.[i])}</span>`).join('')}
    </div>
  `
}

/**
 * 渲染最近练习
 */
function renderRecentPractice(practices) {
  if (practices.length === 0) {
    return '<p class="empty">暂无练习记录</p>'
  }

  return practices.map(p => `
    <div class="practice-item">
      <div class="practice-info">
        <span class="practice-title">${p.title || '练习'}</span>
        <span class="practice-date">${formatDate(p.completed_at)}</span>
      </div>
      <div class="practice-score ${getScoreClass(p.accuracy)}">
        ${((p.accuracy || 0) * 100).toFixed(0)}%
      </div>
    </div>
  `).join('')
}

/**
 * 显示无学生信息
 */
function showNoStudentMessage() {
  const container = document.getElementById('report-container')
  if (!container) return

  container.innerHTML = `
    <div class="empty-state">
      <div style="font-size:3rem;margin-bottom:16px;">📊</div>
      <p>请先登录学生账号</p>
    </div>
  `
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

/**
 * 格式化趋势日期
 */
function formatTrendDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

/**
 * 格式化日期
 */
function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`
}

/**
 * 获取分数样式类
 */
function getScoreClass(accuracy) {
  if (accuracy >= 0.8) return 'excellent'
  if (accuracy >= 0.6) return 'good'
  if (accuracy >= 0.4) return 'warning'
  return 'danger'
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.loadStudentReport = loadStudentReport
}
