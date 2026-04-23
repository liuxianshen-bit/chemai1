/**
 * 教师端 - 报告模块
 */
import { reportService } from '../../services/index.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

// 全局状态
let currentReportData = null

/**
 * 初始化报告模块
 */
export async function initReportModule() {
  const container = document.getElementById('report-teacher-view')
  if (!container) return

  await loadTeacherReport()
}

/**
 * 加载教师报告
 */
export async function loadTeacherReport() {
  const teacherId = getCurrentTeacherId()
  if (!teacherId) return

  showLoading('加载报告...')

  try {
    const result = await reportService.getTeacherReport(teacherId)

    if (result.success) {
      currentReportData = result.data
      renderTeacherReport(result.data)
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
 * 渲染教师报告
 */
function renderTeacherReport(data) {
  // 渲染错误率Top5
  const errorTop5 = document.getElementById('report-error-top5')
  if (errorTop5 && data.error_top5) {
    renderErrorTop5(data.error_top5)
  }

  // 渲染障碍分布
  const obstacleDist = document.getElementById('report-obstacle-distribution')
  if (obstacleDist && data.obstacle_distribution) {
    renderObstacleDistribution(data.obstacle_distribution)
  }

  // 渲染学生列表
  const studentContainer = document.getElementById('report-student-list')
  if (studentContainer && data.students) {
    renderStudentReportList(data.students)
  }
}

/**
 * 渲染错误率Top5
 */
function renderErrorTop5(errors) {
  const container = document.getElementById('report-error-top5-body')
  if (!container) return

  container.innerHTML = errors.map((item, i) => `
    <tr>
      <td style="padding:8px 12px;">${i + 1}</td>
      <td style="padding:8px 12px;">${item.question_content || item.knowledge_point}</td>
      <td style="padding:8px 12px;color:var(--error);">${(item.error_rate * 100).toFixed(1)}%</td>
    </tr>
  `).join('')
}

/**
 * 渲染障碍分布
 */
function renderObstacleDistribution(distribution) {
  const container = document.getElementById('report-obstacle-distribution')
  if (!container) return

  const total = distribution.concept + distribution.reading + distribution.expression

  container.innerHTML = `
    <div class="bar-chart">
      <div class="chart-bars">
        <div class="bar-wrapper">
          <div class="bar concept" style="height: ${(distribution.concept / total * 100)}%"></div>
          <span class="bar-label">${distribution.concept}人</span>
          <span class="bar-title">概念理解</span>
        </div>
        <div class="bar-wrapper">
          <div class="bar reading" style="height: ${(distribution.reading / total * 100)}%"></div>
          <span class="bar-label">${distribution.reading}人</span>
          <span class="bar-title">审题障碍</span>
        </div>
        <div class="bar-wrapper">
          <div class="bar expression" style="height: ${(distribution.expression / total * 100)}%"></div>
          <span class="bar-label">${distribution.expression}人</span>
          <span class="bar-title">表述障碍</span>
        </div>
      </div>
    </div>
  `
}

/**
 * 渲染学生报告列表
 */
function renderStudentReportList(students) {
  const container = document.getElementById('report-student-list')
  if (!container) return

  container.innerHTML = students.map(student => `
    <div class="student-report-card" onclick="viewStudentReportDetail('${student.id}')">
      <div class="student-avatar">${(student.name || 'U').charAt(0)}</div>
      <div class="student-info">
        <h4>${student.name}</h4>
        <p>正确率: ${(student.accuracy * 100).toFixed(1)}%</p>
      </div>
      <div class="student-progress">
        <div class="progress-ring">
          <svg viewBox="0 0 36 36">
            <path class="progress-bg"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path class="progress-fill"
              stroke-dasharray="${student.accuracy * 100}, 100"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
          </svg>
        </div>
      </div>
    </div>
  `).join('')
}

/**
 * 查看学生报告详情
 */
export async function viewStudentReportDetail(studentId) {
  showLoading()

  try {
    const result = await reportService.getStudentReport(studentId)

    if (result.success) {
      renderStudentReportModal(result.data)
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
 * 渲染学生报告弹窗
 */
function renderStudentReportModal(data) {
  const modal = document.getElementById('student-report-modal')
  if (!modal) return

  const content = document.getElementById('student-report-content')
  if (content) {
    content.innerHTML = `
      <div class="report-header">
        <h3>${data.name}</h3>
        <span class="report-date">${formatDate(data.generated_at)}</span>
      </div>

      <div class="report-summary">
        <div class="summary-card">
          <span class="summary-value">${(data.accuracy * 100).toFixed(1)}%</span>
          <span class="summary-label">总体正确率</span>
        </div>
        <div class="summary-card">
          <span class="summary-value">${data.total_questions}</span>
          <span class="summary-label">完成题目</span>
        </div>
        <div class="summary-card">
          <span class="summary-value">${data.correct_count}</span>
          <span class="summary-label">正确数</span>
        </div>
      </div>

      <div class="report-section">
        <h4>知识点掌握情况</h4>
        <div class="kp-mastery-list">
          ${(data.knowledge_mastery || []).map(kp => `
            <div class="kp-item">
              <span class="kp-name">${kp.name}</span>
              <div class="kp-bar">
                <div class="kp-fill" style="width: ${kp.mastery * 100}%"></div>
              </div>
              <span class="kp-value">${(kp.mastery * 100).toFixed(0)}%</span>
            </div>
          `).join('')}
        </div>
      </div>

      <div class="report-section">
        <h4>障碍分析</h4>
        <div class="barrier-summary">
          ${renderBarrierSummary(data.barrier_analysis)}
        </div>
      </div>

      ${data.trend ? `
        <div class="report-section">
          <h4>学习趋势</h4>
          <div class="trend-chart">
            ${renderTrendChart(data.trend)}
          </div>
        </div>
      ` : ''}
    `
  }

  modal.style.display = 'flex'
}

/**
 * 渲染障碍摘要
 */
function renderBarrierSummary(analysis) {
  if (!analysis) return '<p class="empty">暂无障碍数据</p>'

  return `
    <div class="barrier-item">
      <span class="barrier-type concept">概念理解型</span>
      <span class="barrier-count">${analysis.concept_count || 0}次</span>
      <span class="barrier-percent">${((analysis.concept_ratio || 0) * 100).toFixed(1)}%</span>
    </div>
    <div class="barrier-item">
      <span class="barrier-type reading">审题障碍型</span>
      <span class="barrier-count">${analysis.reading_count || 0}次</span>
      <span class="barrier-percent">${((analysis.reading_ratio || 0) * 100).toFixed(1)}%</span>
    </div>
    <div class="barrier-item">
      <span class="barrier-type expression">表述障碍型</span>
      <span class="barrier-count">${analysis.expression_count || 0}次</span>
      <span class="barrier-percent">${((analysis.expression_ratio || 0) * 100).toFixed(1)}%</span>
    </div>
  `
}

/**
 * 渲染趋势图
 */
function renderTrendChart(trend) {
  const points = trend.map((v, i) => `${i * 50},${100 - v * 100}`).join(' ')

  return `
    <svg class="trend-svg" viewBox="0 0 200 100">
      <polyline
        fill="none"
        stroke="var(--accent-cyan)"
        stroke-width="2"
        points="${points}"
      />
    </svg>
    <div class="trend-labels">
      ${trend.map((v, i) => `<span>${formatDate(trend.dates?.[i])}</span>`).join('')}
    </div>
  `
}

/**
 * 格式化日期
 */
function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

/**
 * 获取当前教师ID
 */
function getCurrentTeacherId() {
  const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
  return user.id
}

/**
 * 筛选学生列表
 */
export function filterStudentList(keyword) {
  if (!currentReportData || !currentReportData.students) return

  const filtered = currentReportData.students.filter(s =>
    s.name.includes(keyword) || s.username.includes(keyword)
  )

  renderStudentReportList(filtered)
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.viewStudentReportDetail = viewStudentReportDetail
  window.filterStudentList = filterStudentList
}
