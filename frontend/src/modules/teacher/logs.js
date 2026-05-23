/**
 * 教师端 - 操作日志模块
 */

import { logService } from '../../services/log.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

let logs = []
let currentFilter = {
  action: '',
  target_type: '',
  days: 7
}
let logTypes = []

/**
 * 初始化日志模块
 */
export async function initLogsModule() {
  const container = document.getElementById('logs-container')
  if (!container) return

  showLoading('加载日志数据...')

  try {
    await Promise.all([
      loadLogs(),
      loadLogTypes()
    ])
    renderLogs(container)
  } catch (e) {
    console.error('初始化日志模块失败', e)
    Toast.error('加载失败')
  } finally {
    hideLoading()
  }
}

/**
 * 加载日志数据
 */
async function loadLogs() {
  const result = await logService.getLogs(currentFilter)
  if (result.success) {
    logs = result.logs || []
  } else {
    logs = []
    if (result.message) {
      console.warn('获取日志失败:', result.message)
    }
  }
}

/**
 * 加载日志类型
 */
async function loadLogTypes() {
  const result = await logService.getLogTypes()
  if (result.success) {
    logTypes = result.types || []
  }
}

/**
 * 渲染日志页面
 */
function renderLogs(container) {
  container.innerHTML = `
    <!-- 筛选栏 -->
    <div class="filter-bar" style="display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; align-items: center;">
      <select id="logs-action-select" onchange="logsModule.filterByAction(this.value)"
              style="padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem; min-width: 120px;">
        <option value="">全部操作</option>
        ${logTypes.map(t => `<option value="${t.value}" ${currentFilter.action === t.value ? 'selected' : ''}>${t.label}</option>`).join('')}
      </select>

      <select id="logs-days-select" onchange="logsModule.filterByDays(this.value)"
              style="padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem; min-width: 120px;">
        <option value="7" ${currentFilter.days === 7 ? 'selected' : ''}>最近7天</option>
        <option value="14" ${currentFilter.days === 14 ? 'selected' : ''}>最近14天</option>
        <option value="30" ${currentFilter.days === 30 ? 'selected' : ''}>最近30天</option>
        <option value="90" ${currentFilter.days === 90 ? 'selected' : ''}>最近90天</option>
      </select>

      <button class="btn-secondary" onclick="logsModule.refresh()"
              style="padding: 8px 16px; border-radius: 8px;">
        🔄 刷新
      </button>

      <button class="btn-secondary" onclick="logsModule.exportLogs()"
              style="padding: 8px 16px; border-radius: 8px;">
        📥 导出Excel
      </button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row" style="margin-bottom: 24px;">
      <div class="stat-card teal">
        <div class="stat-label">总记录数</div>
        <div class="stat-value">${logs.length}</div>
      </div>
      <div class="stat-card amber">
        <div class="stat-label">今日操作</div>
        <div class="stat-value">${countTodayLogs()}</div>
      </div>
      <div class="stat-card purple">
        <div class="stat-label">预警操作</div>
        <div class="stat-value">${countWarningLogs()}</div>
      </div>
    </div>

    <!-- 日志列表 -->
    <div class="panel">
      <div class="panel-header">
        <h3 class="panel-title">操作日志</h3>
      </div>
      <div class="panel-body" style="padding: 0;">
        ${logs.length === 0 ? `
          <div class="empty-state" style="padding: 48px;">
            <div style="font-size: 3rem; margin-bottom: 16px;">📋</div>
            <p style="color: var(--text-muted);">暂无日志记录</p>
          </div>
        ` : `
          <table style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="background: var(--bg-tertiary); text-align: left;">
                <th style="padding: 12px 16px; font-size: 0.75rem; color: var(--text-muted); font-weight: 500;">时间</th>
                <th style="padding: 12px 16px; font-size: 0.75rem; color: var(--text-muted); font-weight: 500;">操作人</th>
                <th style="padding: 12px 16px; font-size: 0.75rem; color: var(--text-muted); font-weight: 500;">操作类型</th>
                <th style="padding: 12px 16px; font-size: 0.75rem; color: var(--text-muted); font-weight: 500;">操作详情</th>
                <th style="padding: 12px 16px; font-size: 0.75rem; color: var(--text-muted); font-weight: 500;">IP地址</th>
              </tr>
            </thead>
            <tbody>
              ${logs.map(log => `
                <tr style="border-bottom: 1px solid var(--border-subtle);">
                  <td style="padding: 12px 16px; font-size: 0.8125rem; color: var(--text-secondary);">
                    ${formatTime(log.created_at)}
                  </td>
                  <td style="padding: 12px 16px; font-size: 0.8125rem; color: var(--text-primary);">
                    ${log.user_id || '-'}
                  </td>
                  <td style="padding: 12px 16px; font-size: 0.8125rem;">
                    ${renderActionBadge(log.action)}
                  </td>
                  <td style="padding: 12px 16px; font-size: 0.8125rem; color: var(--text-secondary); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    ${log.detail || '-'}
                  </td>
                  <td style="padding: 12px 16px; font-size: 0.8125rem; color: var(--text-muted);">
                    ${log.ip_address || '-'}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `}
      </div>
    </div>
  `
}

/**
 * 渲染操作类型标签
 */
function renderActionBadge(action) {
  const colors = {
    'login': { bg: 'var(--teal-bg)', color: 'var(--teal)' },
    'logout': { bg: 'var(--bg-tertiary)', color: 'var(--text-secondary)' },
    'create': { bg: 'var(--success)', color: 'white' },
    'update': { bg: 'var(--amber-bg)', color: 'var(--amber)' },
    'delete': { bg: 'var(--error)', color: 'white' },
    'ocr': { bg: 'var(--purple-bg)', color: 'var(--purple)' },
    'exam_create': { bg: 'var(--teal-bg)', color: 'var(--teal)' },
    'exam_submit': { bg: 'var(--accent-bg)', color: 'var(--accent)' },
    'warning': { bg: 'rgba(220, 38, 38, 0.1)', color: 'var(--error)' },
    'notification': { bg: 'var(--amber-bg)', color: 'var(--amber)' },
    'report': { bg: 'var(--purple-bg)', color: 'var(--purple)' }
  }

  const labels = {
    'login': '登录',
    'logout': '登出',
    'create': '创建',
    'update': '更新',
    'delete': '删除',
    'ocr': 'OCR识别',
    'exam_create': '创建考试',
    'exam_submit': '提交考试',
    'warning': '预警',
    'notification': '通知',
    'report': '报告'
  }

  const style = colors[action] || { bg: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }
  const label = labels[action] || action

  return `<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; background: ${style.bg}; color: ${style.color};">${label}</span>`
}

/**
 * 统计今日日志数
 */
function countTodayLogs() {
  const today = new Date().toDateString()
  return logs.filter(log => {
    if (!log.created_at) return false
    return new Date(log.created_at).toDateString() === today
  }).length
}

/**
 * 统计预警日志数
 */
function countWarningLogs() {
  return logs.filter(log => log.action === 'warning').length
}

/**
 * 格式化时间
 */
function formatTime(timeStr) {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / 86400000)

  if (days === 0) {
    return '今天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

/**
 * 按操作类型筛选
 */
export async function filterByAction(action) {
  currentFilter.action = action
  const container = document.getElementById('logs-container')
  if (container) {
    showLoading('加载中...')
    try {
      await loadLogs()
      renderLogs(container)
    } finally {
      hideLoading()
    }
  }
}

/**
 * 按天数筛选
 */
export async function filterByDays(days) {
  currentFilter.days = parseInt(days)
  const container = document.getElementById('logs-container')
  if (container) {
    showLoading('加载中...')
    try {
      await loadLogs()
      renderLogs(container)
    } finally {
      hideLoading()
    }
  }
}

/**
 * 刷新
 */
export async function refresh() {
  const container = document.getElementById('logs-container')
  if (container) {
    showLoading('刷新中...')
    try {
      await loadLogs()
      renderLogs(container)
    } finally {
      hideLoading()
    }
  }
}

/**
 * 导出日志
 */
export function exportLogs() {
  if (logs.length === 0) {
    Toast.error('暂无日志可导出')
    return
  }

  // 生成CSV
  const headers = ['时间', '操作人', '操作类型', '操作详情', 'IP地址']
  const rows = logs.map(log => [
    log.created_at || '',
    log.user_id || '',
    log.action || '',
    (log.detail || '').replace(/"/g, '""'),
    log.ip_address || ''
  ])

  const csvContent = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n')

  // 下载
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `操作日志_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)

  Toast.success('导出成功')
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.logsModule = {
    init: initLogsModule,
    filterByAction,
    filterByDays,
    refresh,
    exportLogs
  }
}

export default {
  init: initLogsModule,
  filterByAction,
  filterByDays,
  refresh,
  exportLogs
}
