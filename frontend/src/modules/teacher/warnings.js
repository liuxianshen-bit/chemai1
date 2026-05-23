/**
 * 教师端 - 预警中心模块
 */

import { warningService } from '../../services/warning.js'
import { notificationService } from '../../services/notification.js'
import { classService } from '../../services/index.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

let warnings = []
let currentFilter = 'pending' // pending, processed, all
let currentClassId = ''
let classes = []

/**
 * 初始化预警模块
 */
export async function initWarningsModule() {
  const container = document.getElementById('warnings-container')
  if (!container) return

  showLoading('加载预警数据...')

  try {
    // 加载班级列表
    await loadClasses()

    // 加载预警数据
    await loadWarnings()
  } catch (e) {
    console.error('初始化预警模块失败', e)
    Toast.error('加载失败')
  } finally {
    hideLoading()
  }
}

/**
 * 加载班级列表
 */
async function loadClasses() {
  const result = await classService.getClassList()
  if (result.success) {
    classes = result.data || []
    renderClassSelect()
  }
}

/**
 * 渲染班级选择器
 */
function renderClassSelect() {
  const select = document.getElementById('warnings-class-select')
  if (!select) return

  select.innerHTML = '<option value="">全部班级</option>' +
    classes.map(c => `<option value="${c.id || c.class_id}">${c.name}</option>`).join('')

  if (currentClassId) {
    select.value = currentClassId
  }
}

/**
 * 加载预警数据
 */
async function loadWarnings() {
  const container = document.getElementById('warnings-container')
  if (!container) return

  try {
    const result = await warningService.getPendingWarnings(getCurrentTeacherId())

    if (result.success || result.warnings) {
      warnings = result.warnings || []
      renderWarnings(container)
    } else {
      container.innerHTML = `
        <div class="empty-state" style="padding: 48px; text-align: center;">
          <div style="font-size: 3rem; margin-bottom: 16px;">✅</div>
          <p style="color: var(--text-muted);">暂无预警数据</p>
        </div>
      `
    }
  } catch (e) {
    console.error('加载预警失败', e)
    container.innerHTML = `
      <div class="empty-state" style="padding: 48px; text-align: center;">
        <div style="font-size: 3rem; margin-bottom: 16px;">❌</div>
        <p style="color: var(--text-muted);">加载失败</p>
      </div>
    `
  }
}

/**
 * 渲染预警列表
 */
function renderWarnings(container) {
  const filteredWarnings = filterWarnings(warnings)
  const stats = calculateStats(warnings)

  container.innerHTML = `
    <!-- 统计卡片 -->
    <div class="stats-row" style="margin-bottom: 24px;">
      <div class="stat-card red">
        <div class="stat-label">高危预警</div>
        <div class="stat-value">${stats.high}</div>
      </div>
      <div class="stat-card amber">
        <div class="stat-label">中危预警</div>
        <div class="stat-value">${stats.medium}</div>
      </div>
      <div class="stat-card green">
        <div class="stat-label">已处理</div>
        <div class="stat-value">${stats.processed}</div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar" style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center;">
      <select id="warnings-class-select" onchange="warningsModule.filterByClass(this.value)"
              style="padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        <option value="">全部班级</option>
      </select>

      <div style="display: flex; gap: 8px; flex: 1;">
        <button class="filter-btn ${currentFilter === 'pending' ? 'active' : ''}"
                onclick="warningsModule.switchFilter('pending')"
                style="padding: 8px 16px; border: none; border-radius: 20px; font-size: 0.8125rem; cursor: pointer;
                       ${currentFilter === 'pending' ? 'background: var(--error); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
          待处理 (${stats.pending})
        </button>
        <button class="filter-btn ${currentFilter === 'processed' ? 'active' : ''}"
                onclick="warningsModule.switchFilter('processed')"
                style="padding: 8px 16px; border: none; border-radius: 20px; font-size: 0.8125rem; cursor: pointer;
                       ${currentFilter === 'processed' ? 'background: var(--success); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
          已处理 (${stats.processed})
        </button>
        <button class="filter-btn ${currentFilter === 'all' ? 'active' : ''}"
                onclick="warningsModule.switchFilter('all')"
                style="padding: 8px 16px; border: none; border-radius: 20px; font-size: 0.8125rem; cursor: pointer;
                       ${currentFilter === 'all' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
          全部
        </button>
      </div>

      <button class="btn-secondary" onclick="warningsModule.refresh()"
              style="padding: 8px 16px; border-radius: 8px;">
        🔄 刷新
      </button>
    </div>

    <!-- 预警列表 -->
    <div class="warnings-list">
      ${filteredWarnings.length === 0 ? `
        <div class="empty-state" style="padding: 48px; text-align: center;">
          <div style="font-size: 3rem; margin-bottom: 16px;">✅</div>
          <p style="color: var(--text-muted);">暂无相关预警</p>
        </div>
      ` : filteredWarnings.map(w => renderWarningCard(w)).join('')}
    </div>
  `

  // 渲染班级选择器
  renderClassSelect()
}

/**
 * 过滤预警
 */
function filterWarnings(warnings) {
  let filtered = warnings

  if (currentClassId) {
    filtered = filtered.filter(w => w.class_id === currentClassId)
  }

  if (currentFilter === 'pending') {
    filtered = filtered.filter(w => w.status !== 'processed' && w.status !== 'ignored')
  } else if (currentFilter === 'processed') {
    filtered = filtered.filter(w => w.status === 'processed' || w.status === 'ignored')
  }

  return filtered
}

/**
 * 计算统计
 */
function calculateStats(warnings) {
  const stats = { high: 0, medium: 0, pending: 0, processed: 0 }

  warnings.forEach(w => {
    const level = w.level || w.warning_level || 'medium'
    if (level === 'high' || level === 'red') stats.high++
    if (level === 'medium' || level === 'amber') stats.medium++
    if (w.status === 'processed' || w.status === 'ignored') stats.processed++
    if (w.status !== 'processed' && w.status !== 'ignored') stats.pending++
  })

  return stats
}

/**
 * 渲染单个预警卡片
 */
function renderWarningCard(w) {
  const levelNames = {
    'high': '高危',
    'medium': '中危',
    'low': '低危'
  }

  const levelColors = {
    'high': 'var(--error)',
    'medium': 'var(--warning)',
    'low': 'var(--success)'
  }

  const levelBgColors = {
    'high': 'rgba(220, 38, 38, 0.1)',
    'medium': 'rgba(245, 158, 11, 0.1)',
    'low': 'rgba(5, 150, 105, 0.1)'
  }

  const statusNames = {
    'pending': '待处理',
    'processed': '已处理',
    'ignored': '已忽略'
  }

  const level = w.level || w.warning_level || 'medium'
  const status = w.status || 'pending'

  return `
    <div class="warning-card" style="
      background: var(--bg-card);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
      border-left: 4px solid ${levelColors[level] || 'var(--warning)'};
    ">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            background: ${levelBgColors[level] || levelBgColors.medium};
            color: ${levelColors[level] || 'var(--warning)'};
          ">
            ${levelNames[level] || '中危'}
          </span>
          <span style="font-weight: 600; color: var(--text-primary);">
            ${w.student_name || w.name || '未知学生'}
          </span>
        </div>
        <span style="font-size: 0.75rem; color: var(--text-muted);">
          ${formatTime(w.created_at || w.timestamp)}
        </span>
      </div>

      <div style="font-size: 0.9375rem; color: var(--text-primary); margin-bottom: 12px;">
        ${w.description || w.content || w.message || '暂无描述'}
      </div>

      ${w.details ? `
        <div style="font-size: 0.8125rem; color: var(--text-secondary); background: var(--bg-tertiary); padding: 8px 12px; border-radius: 6px; margin-bottom: 12px;">
          ${w.details}
        </div>
      ` : ''}

      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        ${status === 'pending' ? `
          <button class="btn-primary btn-sm" onclick="warningsModule.sendReminder('${w.warning_id || w.id}')"
                  style="padding: 6px 12px; font-size: 0.8125rem; border-radius: 6px;">
            📤 发送提醒
          </button>
          <button class="btn-secondary btn-sm" onclick="warningsModule.contactParent('${w.warning_id || w.id}')"
                  style="padding: 6px 12px; font-size: 0.8125rem; border-radius: 6px;">
            📱 联系家长
          </button>
          <button class="btn-secondary btn-sm" onclick="warningsModule.ignoreWarning('${w.warning_id || w.id}')"
                  style="padding: 6px 12px; font-size: 0.8125rem; border-radius: 6px;">
            忽略
          </button>
        ` : `
          <span style="font-size: 0.8125rem; color: var(--success);">
            ✓ ${statusNames[status]}
          </span>
        `}
      </div>
    </div>
  `
}

/**
 * 格式化时间
 */
function formatTime(timeStr) {
  if (!timeStr) return ''

  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date

  const days = Math.floor(diff / 86400000)
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

/**
 * 获取当前教师ID
 */
function getCurrentTeacherId() {
  try {
    const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
    return user.teacher_id || user.id
  } catch {
    return null
  }
}

/**
 * 切换筛选
 */
export function switchFilter(filter) {
  currentFilter = filter
  const container = document.getElementById('warnings-container')
  if (container) {
    renderWarnings(container)
  }
}

/**
 * 按班级筛选
 */
export function filterByClass(classId) {
  currentClassId = classId
  const container = document.getElementById('warnings-container')
  if (container) {
    renderWarnings(container)
  }
}

/**
 * 刷新
 */
export async function refresh() {
  await initWarningsModule()
}

/**
 * 发送提醒
 */
export async function sendReminder(warningId) {
  try {
    const result = await warningService.processWarning(
      warningId,
      getCurrentTeacherId(),
      '发送提醒'
    )

    if (result.success) {
      Toast.success('已发送提醒')
      await refresh()
    } else {
      Toast.error('发送失败')
    }
  } catch (e) {
    Toast.error('发送失败：' + e.message)
  }
}

/**
 * 联系家长
 */
export async function contactParent(warningId) {
  const warning = warnings.find(w => (w.warning_id || w.id) === warningId)
  if (!warning) return

  const studentId = warning.student_id

  if (confirm(`确定要向 ${warning.student_name || '该学生'} 的家长发送通知吗？`)) {
    try {
      const result = await notificationService.sendToParent(
        studentId,
        'warning',
        '学情预警提醒',
        `您的孩子${warning.student_name}最近学习情况需要关注：${warning.description || warning.message || '请查看详情'}`
      )

      if (result.success) {
        Toast.success('已发送通知给家长')
        await warningService.processWarning(warningId, getCurrentTeacherId(), '联系家长')
        await refresh()
      } else {
        Toast.error(result.message || '发送失败')
      }
    } catch (e) {
      Toast.error('发送失败：' + e.message)
    }
  }
}

/**
 * 忽略预警
 */
export async function ignoreWarning(warningId) {
  if (!confirm('确定要忽略此预警吗？')) return

  try {
    const result = await warningService.ignoreWarning(
      warningId,
      getCurrentTeacherId(),
      '教师手动忽略'
    )

    if (result.success) {
      Toast.success('已忽略预警')
      await refresh()
    } else {
      Toast.error('操作失败')
    }
  } catch (e) {
    Toast.error('操作失败：' + e.message)
  }
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.warningsModule = {
    init: initWarningsModule,
    switchFilter,
    filterByClass,
    refresh,
    sendReminder,
    contactParent,
    ignoreWarning
  }
}

export default {
  init: initWarningsModule,
  switchFilter,
  filterByClass,
  refresh,
  sendReminder,
  contactParent,
  ignoreWarning
}
