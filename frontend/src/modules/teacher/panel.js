/**
 * 教师端 - 学情面板模块
 */
import { reportService, classService } from '../../services/index.js'
import { api } from '../../services/api.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

// 全局状态
let currentPanelData = null
let currentClassId = null
let currentViewMode = 'class' // 'class' 或 'student'
let currentSelectedStudentId = null
let currentStudentList = []

/**
 * 初始化面板模块
 */
export async function initPanelModule() {
  const container = document.getElementById('panel-container')
  if (!container) return

  await loadPanelData()
}

/**
 * 加载面板数据
 */
export async function loadPanelData(classId) {
  currentClassId = classId

  showLoading('加载面板数据...')

  try {
    const [classResult, reportResult] = await Promise.all([
      classService.getClassList(),
      reportService.getTeacherReport(getCurrentTeacherId())
    ])

    if (classResult.success) {
      const classes = classResult.data || []
      if (classes.length > 0 && !currentClassId) {
        currentClassId = classes[0].id
      }
    }

    if (reportResult.success) {
      currentPanelData = reportResult.data
      renderPanel(reportResult.data)
    } else {
      Toast.error('加载面板数据失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 渲染面板
 */
function renderPanel(data) {
  const container = document.getElementById('panel-container')
  if (!container) return

  // 根据视图模式渲染不同内容
  if (currentViewMode === 'student' && currentSelectedStudentId) {
    renderStudentPanel(data)
  } else {
    renderClassPanel(data)
  }
}

/**
 * 渲染班级整体视图
 */
function renderClassPanel(data) {
  const container = document.getElementById('panel-container')
  if (!container) return

  container.innerHTML = `
    <div class="panel-page">
      <!-- 概览统计 -->
      <div class="panel-overview">
        <div class="overview-card">
          <div class="overview-icon cyan">👨‍🎓</div>
          <div class="overview-info">
            <span class="overview-value">${data.student_count || 0}</span>
            <span class="overview-label">学生总数</span>
          </div>
        </div>
        <div class="overview-card">
          <div class="overview-icon amber">📝</div>
          <div class="overview-info">
            <span class="overview-value">${data.exam_count || 0}</span>
            <span class="overview-label">考试次数</span>
          </div>
        </div>
        <div class="overview-card">
          <div class="overview-icon green">✅</div>
          <div class="overview-info">
            <span class="overview-value">${((data.average_accuracy || 0) * 100).toFixed(0)}%</span>
            <span class="overview-label">平均正确率</span>
          </div>
        </div>
        <div class="overview-card">
          <div class="overview-icon purple">📊</div>
          <div class="overview-info">
            <span class="overview-value">${data.completion_rate || 0}%</span>
            <span class="overview-label">完成率</span>
          </div>
        </div>
      </div>

      <!-- 成绩趋势 -->
      <section class="panel-section">
        <h3 class="section-title">班级成绩趋势</h3>
        <div class="score-trend-chart" id="score-trend-chart">
          ${renderScoreTrend(data.score_trend)}
        </div>
      </section>

      <!-- 障碍分布 -->
      <section class="panel-section">
        <h3 class="section-title">障碍类型分布</h3>
        <div class="barrier-distribution">
          ${renderBarrierDistribution(data.obstacle_distribution)}
        </div>
      </section>

      <!-- 学生卡片列表 - 可点击 -->
      <section class="panel-section">
        <h3 class="section-title">学生详情（点击查看）</h3>

        <!-- 搜索和筛选工具栏 -->
        <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;align-items:center;">
          <div style="position:relative;flex:1;min-width:200px;">
            <input type="text" id="student-search-input" placeholder="搜索学生姓名或学号..."
              oninput="window.filterStudentCards(this.value)"
              style="width:100%;padding:10px 12px 10px 36px;border:1px solid var(--border);border-radius:8px;font-size:0.875rem;">
            <svg style="position:absolute;left:12px;top:50%;transform:translateY(-50%);width:16px;height:16px;color:var(--text-muted);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
          <select id="student-filter-barrier" onchange="window.filterStudentCards(document.getElementById('student-search-input').value)"
            style="padding:10px 12px;border:1px solid var(--border);border-radius:8px;font-size:0.875rem;min-width:120px;">
            <option value="">全部障碍</option>
            <option value="concept">概念理解型</option>
            <option value="reading">审题障碍型</option>
            <option value="expression">表述障碍型</option>
          </select>
          <select id="student-sort" onchange="window.sortStudentCards(this.value)"
            style="padding:10px 12px;border:1px solid var(--border);border-radius:8px;font-size:0.875rem;min-width:120px;">
            <option value="name">按姓名</option>
            <option value="accuracy-desc">正确率↓</option>
            <option value="accuracy-asc">正确率↑</option>
            <option value="barrier">按障碍类型</option>
          </select>
        </div>

        <!-- 学生卡片网格 -->
        <div class="student-cards-grid" id="student-cards-grid">
          ${renderStudentCards(data.student_progress || [])}
        </div>

        <!-- 无结果提示 -->
        <div id="student-search-empty" style="display:none;text-align:center;padding:32px;color:var(--text-muted);">
          <div style="font-size:2rem;margin-bottom:8px;">🔍</div>
          <div>没有找到匹配的学生</div>
        </div>
      </section>

      <!-- 班级对比 -->
      <section class="panel-section">
        <h3 class="section-title">班级对比</h3>
        <div class="class-comparison">
          ${renderClassComparison(data.class_comparison)}
        </div>
      </section>
    </div>
  `

  // 保存原始学生数据供筛选使用
  window._allStudentsData = data.student_progress || []
}

/**
 * 筛选学生卡片
 */
function filterStudentCards(searchText) {
  const barrierFilter = document.getElementById('student-filter-barrier')?.value || ''
  const sortValue = document.getElementById('student-sort')?.value || 'name'
  const allStudents = window._allStudentsData || []

  let filtered = allStudents.filter(s => {
    const matchSearch = !searchText ||
      (s.name && s.name.toLowerCase().includes(searchText.toLowerCase())) ||
      (s.student_id && s.student_id.toLowerCase().includes(searchText.toLowerCase()))

    const dominantBarrier = getDominantBarrier(s.barrier_type)
    const matchBarrier = !barrierFilter || dominantBarrier === barrierFilter

    return matchSearch && matchBarrier
  })

  // 排序
  filtered = sortStudents(filtered, sortValue)

  // 渲染
  const grid = document.getElementById('student-cards-grid')
  const empty = document.getElementById('student-search-empty')

  if (grid) {
    grid.innerHTML = filtered.length > 0 ? renderStudentCards(filtered) : ''
    grid.style.display = filtered.length > 0 ? '' : 'none'
  }

  if (empty) {
    empty.style.display = filtered.length === 0 ? 'block' : 'none'
  }
}

/**
 * 排序学生卡片
 */
function sortStudents(students, sortValue) {
  const sorted = [...students]

  switch (sortValue) {
    case 'name':
      sorted.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'zh-CN'))
      break
    case 'accuracy-desc':
      sorted.sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0))
      break
    case 'accuracy-asc':
      sorted.sort((a, b) => (a.accuracy || 0) - (b.accuracy || 0))
      break
    case 'barrier':
      sorted.sort((a, b) => {
        const barrierOrder = { 'concept': 0, 'reading': 1, 'expression': 2 }
        const aBarrier = getDominantBarrier(a.barrier_type) || 'concept'
        const bBarrier = getDominantBarrier(b.barrier_type) || 'concept'
        return (barrierOrder[aBarrier] || 0) - (barrierOrder[bBarrier] || 0)
      })
      break
  }

  return sorted
}

/**
 * 获取主要障碍类型
 */
function getDominantBarrier(barrierType) {
  if (!barrierType) return 'concept'
  const entries = Object.entries(barrierType)
  if (entries.length === 0) return 'concept'
  entries.sort((a, b) => b[1] - a[1])
  return entries[0][0]
}

/**
 * 快捷筛选（供外部调用）
 */
function quickFilterByBarrier(barrierType) {
  const filterSelect = document.getElementById('student-filter-barrier')
  if (filterSelect) {
    filterSelect.value = barrierType
  }
  filterStudentCards(document.getElementById('student-search-input')?.value || '')
}

/**
 * 渲染学生卡片列表（可点击）
 */
function renderStudentCards(students) {
  if (students.length === 0) {
    return '<p class="empty">暂无学生数据</p>'
  }

  return `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;">
      ${students.map(s => `
        <div class="student-card" onclick="teacherModule.selectPanelStudent('${s.student_id}')"
          style="padding:16px;background:var(--bg);border-radius:12px;cursor:pointer;transition:all 0.2s;border:1px solid var(--border);"
          onmouseover="this.style.borderColor='var(--accent)';this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)';"
          onmouseout="this.style.borderColor='var(--border)';this.style.boxShadow='none';">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--teal));display:flex;align-items:center;justify-content:center;color:white;font-weight:600;">
              ${(s.name || 'U').charAt(0)}
            </div>
            <div>
              <div style="font-weight:600;color:var(--text-primary);">${s.name || '未知'}</div>
              <div style="font-size:0.75rem;color:var(--text-muted);">${s.class_name || ''}</div>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.8125rem;">
            <div style="padding:8px;background:var(--bg-tertiary);border-radius:6px;text-align:center;">
              <div style="color:${(s.accuracy || 0) >= 0.7 ? 'var(--success)' : 'var(--warning)'};font-weight:600;">
                ${((s.accuracy || 0) * 100).toFixed(0)}%
              </div>
              <div style="color:var(--text-muted);font-size:0.6875rem;">正确率</div>
            </div>
            <div style="padding:8px;background:var(--bg-tertiary);border-radius:6px;text-align:center;">
              <div style="color:var(--accent);font-weight:600;">
                ${getBarrierTypeName(s.barrier_type ? Object.entries(s.barrier_type).sort((a,b)=>b[1]-a[1])[0][0] : 'concept')}
              </div>
              <div style="color:var(--text-muted);font-size:0.6875rem;">主要障碍</div>
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `
}

/**
 * 渲染单一学生视图
 */
function renderStudentPanel(data) {
  const container = document.getElementById('panel-container')
  if (!container) return

  // 找到选中学生的数据
  const studentData = data.student_progress?.find(s => s.student_id === currentSelectedStudentId)

  container.innerHTML = `
    <div class="panel-page">
      <!-- 返回按钮 -->
      <div style="margin-bottom:24px;">
        <button class="btn btn-secondary" onclick="teacherModule.switchPanelView('class')">
          ← 返回班级整体
        </button>
      </div>

      ${studentData ? renderStudentDetail(studentData, data) : renderNoStudentData()}
    </div>
  `
}

/**
 * 渲染学生详情
 */
function renderStudentDetail(student, data) {
  // 计算该学生的历史诊断信息
  const barrierType = student.barrier_type || { concept: 0.33, reading: 0.33, expression: 0.34 }
  const dominantBarrier = student.dominant_barrier || 'concept'

  return `
    <!-- 学生概览 -->
    <div class="panel-overview">
      <div class="overview-card">
        <div class="overview-icon cyan">👤</div>
        <div class="overview-info">
          <span class="overview-value">${student.name || '未知'}</span>
          <span class="overview-label">学生姓名</span>
        </div>
      </div>
      <div class="overview-card">
        <div class="overview-icon green">✅</div>
        <div class="overview-info">
          <span class="overview-value">${((student.accuracy || 0) * 100).toFixed(0)}%</span>
          <span class="overview-label">正确率</span>
        </div>
      </div>
      <div class="overview-card">
        <div class="overview-icon amber">📝</div>
        <div class="overview-info">
          <span class="overview-value">${student.completed_count || 0}/${student.total_count || 0}</span>
          <span class="overview-label">完成情况</span>
        </div>
      </div>
      <div class="overview-card">
        <div class="overview-icon purple">🎯</div>
        <div class="overview-info">
          <span class="overview-value">${getBarrierTypeName(dominantBarrier)}</span>
          <span class="overview-label">主要障碍</span>
        </div>
      </div>
    </div>

    <!-- 学生障碍分布 -->
    <section class="panel-section">
      <h3 class="section-title">障碍类型分布</h3>
      <div class="barrier-distribution">
        ${renderBarrierDistribution(barrierType)}
      </div>
    </section>

    <!-- 薄弱知识点 -->
    <section class="panel-section">
      <h3 class="section-title">薄弱知识点</h3>
      <div class="weak-kps-list" style="display:flex;flex-wrap:wrap;gap:8px;">
        ${(student.weak_knowledge_points || ['暂无数据']).map(kp => `
          <span style="padding:6px 12px;background:var(--accent-bg);color:var(--accent);border-radius:16px;font-size:0.875rem;">
            ${kp}
          </span>
        `).join('')}
      </div>
    </section>

    <!-- 学习历史 -->
    <section class="panel-section">
      <h3 class="section-title">学习历史</h3>
      <div class="student-history">
        ${renderStudentHistory(student)}
      </div>
    </section>

    <!-- 学习计划 -->
    <section class="panel-section">
      <h3 class="section-title">个性化学习计划</h3>
      <div class="learning-plan" style="padding:16px;background:var(--bg-tertiary);border-radius:12px;">
        <div style="margin-bottom:12px;">
          <strong style="color:var(--accent);">当前计划：</strong>
          <span style="color:var(--text-secondary);">基于${getBarrierTypeName(dominantBarrier)}制定的专项提升方案</span>
        </div>
        <button class="btn btn-primary" onclick="window.generateLearningPlan('${currentSelectedStudentId}')">
          生成新学习计划
        </button>
      </div>
    </section>
  `
}

/**
 * 渲染无学生数据状态
 */
function renderNoStudentData() {
  return `
    <div class="empty-state" style="padding:48px;text-align:center;">
      <div class="empty-state-icon" style="font-size:3rem;margin-bottom:16px;">👤</div>
      <p style="color:var(--text-muted);">请从上方选择一名学生查看详情</p>
    </div>
  `
}

/**
 * 渲染学生学习历史
 */
function renderStudentHistory(student) {
  // 模拟历史数据，实际应从API获取
  const historyItems = student.history || [
    { date: '2026-04-15', exam: '氧化还原反应测验', score: 72, barrier: 'concept' },
    { date: '2026-04-10', exam: '离子反应测验', score: 85, barrier: 'reading' },
    { date: '2026-04-05', exam: '化学平衡测验', score: 68, barrier: 'expression' }
  ]

  return `
    <div style="display:flex;flex-direction:column;gap:12px;">
      ${historyItems.map(item => `
        <div style="display:flex;align-items:center;gap:16px;padding:12px;background:var(--bg);border-radius:8px;">
          <span style="font-size:0.75rem;color:var(--text-muted);min-width:80px;">${item.date}</span>
          <span style="flex:1;">${item.exam}</span>
          <span style="color:${item.score >= 70 ? 'var(--success)' : 'var(--warning)'};">${item.score}分</span>
          <span style="font-size:0.75rem;padding:2px 8px;background:var(--bg-tertiary);border-radius:4px;">
            ${getBarrierTypeName(item.barrier)}
          </span>
        </div>
      `).join('')}
    </div>
  `
}

/**
 * 获取障碍类型名称
 */
function getBarrierTypeName(barrier) {
  const names = {
    'concept': '概念理解型',
    'reading': '审题障碍型',
    'expression': '表述障碍型'
  }
  return names[barrier] || barrier
}

/**
 * 渲染成绩趋势图
 */
function renderScoreTrend(trend) {
  if (!trend || trend.length === 0) {
    return '<p class="empty">暂无趋势数据</p>'
  }

  const maxScore = 100
  const points = trend.map((v, i) => {
    const x = (i / (trend.length - 1)) * 300
    const y = 100 - v
    return `${x},${y}`
  }).join(' ')

  const avg = trend.reduce((a, b) => a + b, 0) / trend.length
  const avgY = 100 - avg

  return `
    <div class="trend-container">
      <svg class="trend-svg" viewBox="0 0 300 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--accent-cyan)" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="var(--accent-cyan)" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <!-- 网格线 -->
        <line x1="0" y1="25" x2="300" y2="25" stroke="var(--border-subtle)" stroke-dasharray="4"/>
        <line x1="0" y1="50" x2="300" y2="50" stroke="var(--border-subtle)" stroke-dasharray="4"/>
        <line x1="0" y1="75" x2="300" y2="75" stroke="var(--border-subtle)" stroke-dasharray="4"/>
        <!-- 平均线 -->
        <line x1="0" y1="${avgY}" x2="300" y2="${avgY}" stroke="var(--accent-amber)" stroke-width="1" stroke-dasharray="4"/>
        <!-- 趋势线 -->
        <polyline
          fill="none"
          stroke="var(--accent-cyan)"
          stroke-width="2"
          points="${points}"
        />
        <polygon
          fill="url(#scoreGradient)"
          points="0,100 ${points} 300,100"
        />
      </svg>
      <div class="trend-labels">
        ${trend.map((v, i) => `<span>${formatTrendDate(trend.dates?.[i])}</span>`).join('')}
      </div>
      <div class="trend-legend">
        <span class="legend-line cyan"></span> 成绩趋势
        <span class="legend-line amber"></span> 平均 ${avg.toFixed(0)}分
      </div>
    </div>
  `
}

/**
 * 渲染障碍分布
 */
function renderBarrierDistribution(distribution) {
  if (!distribution) {
    return '<p class="empty">暂无障碍数据</p>'
  }

  const total = (distribution.concept || 0) + (distribution.reading || 0) + (distribution.expression || 0)

  return `
    <div class="barrier-overview">
      <div class="barrier-chart-container">
        <svg viewBox="0 0 100 100">
          ${renderPieChart(distribution, total)}
        </svg>
      </div>
      <div class="barrier-legend">
        <div class="legend-item">
          <span class="legend-color concept"></span>
          <span class="legend-text">概念理解型</span>
          <span class="legend-count">${distribution.concept || 0}</span>
          <span class="legend-percent">${total > 0 ? ((distribution.concept || 0) / total * 100).toFixed(0) : 0}%</span>
        </div>
        <div class="legend-item">
          <span class="legend-color reading"></span>
          <span class="legend-text">审题障碍型</span>
          <span class="legend-count">${distribution.reading || 0}</span>
          <span class="legend-percent">${total > 0 ? ((distribution.reading || 0) / total * 100).toFixed(0) : 0}%</span>
        </div>
        <div class="legend-item">
          <span class="legend-color expression"></span>
          <span class="legend-text">表述障碍型</span>
          <span class="legend-count">${distribution.expression || 0}</span>
          <span class="legend-percent">${total > 0 ? ((distribution.expression || 0) / total * 100).toFixed(0) : 0}%</span>
        </div>
      </div>
    </div>
  `
}

/**
 * 渲染饼图
 */
function renderPieChart(distribution, total) {
  if (total === 0) {
    return '<circle cx="50" cy="50" r="40" fill="var(--bg-tertiary)"/>'
  }

  const concept = (distribution.concept || 0) / total * 360
  const reading = (distribution.reading || 0) / total * 360
  const expression = (distribution.expression || 0) / total * 360

  let path = ''
  let currentAngle = -90

  // 概念理解
  if (concept > 0) {
    path += createPieSlice(50, 50, 40, currentAngle, concept, 'var(--barrier-concept)')
    currentAngle += concept
  }
  // 审题障碍
  if (reading > 0) {
    path += createPieSlice(50, 50, 40, currentAngle, reading, 'var(--barrier-reading)')
    currentAngle += reading
  }
  // 表述障碍
  if (expression > 0) {
    path += createPieSlice(50, 50, 40, currentAngle, expression, 'var(--barrier-expression)')
  }

  return path
}

/**
 * 创建饼图切片
 */
function createPieSlice(cx, cy, r, startAngle, endAngle, color) {
  const start = polarToCartesian(cx, cy, r, startAngle)
  const end = polarToCartesian(cx, cy, r, startAngle + endAngle)
  const largeArc = endAngle > 180 ? 1 : 0

  return `<path d="M${cx},${cy}L${start.x},${start.y}A${r},${r}0,${largeArc},1,${end.x},${end.y}Z" fill="${color}"/>`
}

/**
 * 极坐标转笛卡尔坐标
 */
function polarToCartesian(cx, cy, r, angle) {
  const rad = (angle * Math.PI) / 180
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad)
  }
}

/**
 * 渲染学生进度列表
 */
function renderStudentProgress(progress) {
  if (progress.length === 0) {
    return '<p class="empty">暂无学生数据</p>'
  }

  return `
    <div class="progress-cards">
      ${progress.slice(0, 5).map(s => `
        <div class="progress-card">
          <div class="progress-header">
            <div class="student-avatar">${(s.name || 'U').charAt(0)}</div>
            <div class="student-info">
              <span class="student-name">${s.name}</span>
              <span class="student-class">${s.class_name || ''}</span>
            </div>
          </div>
          <div class="progress-stats">
            <div class="progress-stat">
              <span class="stat-value">${((s.accuracy || 0) * 100).toFixed(0)}%</span>
              <span class="stat-label">正确率</span>
            </div>
            <div class="progress-stat">
              <span class="stat-value">${s.completed_count || 0}/${s.total_count || 0}</span>
              <span class="stat-label">完成</span>
            </div>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${(s.accuracy || 0) * 100}%"></div>
          </div>
        </div>
      `).join('')}
    </div>
    ${progress.length > 5 ? `<p class="more-hint">还有 ${progress.length - 5} 名学生...</p>` : ''}
  `
}

/**
 * 渲染班级对比
 */
function renderClassComparison(comparison) {
  if (!comparison || comparison.length === 0) {
    return '<p class="empty">暂无对比数据</p>'
  }

  return `
    <div class="comparison-chart">
      <div class="comparison-bars">
        ${comparison.map(c => `
          <div class="comparison-item">
            <span class="comparison-label">${c.name}</span>
            <div class="comparison-bar-wrapper">
              <div class="comparison-bar" style="width: ${(c.accuracy || 0) * 100}%"></div>
            </div>
            <span class="comparison-value">${((c.accuracy || 0) * 100).toFixed(0)}%</span>
          </div>
        `).join('')}
      </div>
    </div>
  `
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
 * 获取当前教师ID
 */
function getCurrentTeacherId() {
  try {
    const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
    return user.id
  } catch {
    return null
  }
}

/**
 * 切换面板视图模式
 */
export function switchPanelView(viewMode) {
  currentViewMode = viewMode
  if (viewMode === 'student' && !currentSelectedStudentId && currentStudentList.length > 0) {
    currentSelectedStudentId = currentStudentList[0].student_id
  }
  renderPanel(currentPanelData)
}

/**
 * 选择面板学生
 */
export function selectPanelStudent(studentId) {
  currentSelectedStudentId = studentId
  renderPanel(currentPanelData)
}

/**
 * 加载学生列表
 */
export async function loadStudentList() {
  try {
    const result = await classService.getClassStudents(currentClassId)
    if (result.success) {
      currentStudentList = result.data || []
    }
  } catch (error) {
    console.error('加载学生列表失败:', error)
  }
}

/**
 * 生成学生学习计划
 */
export async function generateLearningPlan(studentId) {
  if (!studentId) {
    Toast.error('请先选择学生')
    return
  }

  Toast.info('正在生成学习计划...')

  try {
    // 调用学习计划生成API
    const student = currentStudentList.find(s => s.student_id === studentId)
    const result = await api.post('/api/diagnosis/learning-plan/generate', {
      student_id: studentId,
      barrier_type: student?.dominant_barrier || student?.barrier_type?.dominant || 'concept',
      weak_knowledge_points: student?.weak_knowledge_points || []
    })

    if (result.success || result.student_id) {
      Toast.success('学习计划已生成')
    } else {
      Toast.error('生成失败')
    }
  } catch (error) {
    Toast.error('生成失败：' + error.message)
  }
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.loadPanelData = loadPanelData
  window.switchPanelView = switchPanelView
  window.selectPanelStudent = selectPanelStudent
  window.generateLearningPlan = generateLearningPlan
  window.filterStudentCards = filterStudentCards
  window.sortStudentCards = sortStudents
  window.quickFilterByBarrier = quickFilterByBarrier
}
