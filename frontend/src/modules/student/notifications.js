/**
 * 学生端 - 通知中心模块
 */

import { notificationService } from '../../services/notification.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

let notifications = []
let currentPage = 0
let currentFilter = 'all' // all, unread, warning, report, review
const pageSize = 20

/**
 * 初始化通知中心
 */
export async function initNotificationsModule() {
  const container = document.getElementById('notifications-content')
  if (!container) return

  currentPage = 0
  notifications = []
  currentFilter = 'all'
  await loadNotifications(container)
}

/**
 * 加载通知列表
 */
async function loadNotifications(container, append = false) {
  if (!append) {
    showLoading('加载中...')
  }

  try {
    const studentId = getCurrentStudentId()
    if (!studentId) {
      Toast.error('未登录')
      return
    }

    const result = await notificationService.getStudentNotifications(studentId, pageSize, currentPage * pageSize)

    if (result.success || result.notifications) {
      const newNotifications = result.notifications || []

      if (append) {
        notifications = [...notifications, ...newNotifications]
      } else {
        notifications = newNotifications
      }

      if (notifications.length > 0) {
        renderNotifications(container)
      } else {
        container.innerHTML = `
          <div class="empty-state" style="padding: 48px; text-align: center;">
            <div style="font-size: 3rem; margin-bottom: 16px;">🔔</div>
            <p style="color: var(--text-muted);">暂无通知</p>
          </div>
        `
      }
    } else {
      container.innerHTML = `
        <div class="empty-state" style="padding: 48px; text-align: center;">
          <div style="font-size: 3rem; margin-bottom: 16px;">❌</div>
          <p style="color: var(--text-muted);">加载失败</p>
        </div>
      `
    }
  } catch (error) {
    console.error('加载通知失败:', error)
    container.innerHTML = `
      <div class="empty-state" style="padding: 48px; text-align: center;">
        <div style="font-size: 3rem; margin-bottom: 16px;">❌</div>
        <p style="color: var(--text-muted);">加载失败，请重试</p>
      </div>
    `
  } finally {
    hideLoading()
  }
}

/**
 * 渲染通知列表
 */
function renderNotifications(container) {
  const filtered = filterNotifications(notifications)

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 48px; text-align: center;">
        <div style="font-size: 3rem; margin-bottom: 16px;">🔔</div>
        <p style="color: var(--text-muted);">暂无相关通知</p>
      </div>
    `
    return
  }

  container.innerHTML = `
    <div class="notifications-list">
      ${filtered.map(n => renderNotificationItem(n)).join('')}
    </div>
    ${filtered.length >= pageSize ? `
      <div class="load-more" onclick="studentNotificationsModule.loadMore()">
        加载更多
      </div>
    ` : ''}
  `
}

/**
 * 过滤通知
 */
function filterNotifications(notifications) {
  if (currentFilter === 'all') return notifications
  if (currentFilter === 'unread') return notifications.filter(n => !n.is_read)
  if (currentFilter === 'warning') return notifications.filter(n => n.type === 'warning' || n.type === 'score_alert')
  if (currentFilter === 'report') return notifications.filter(n => n.type === 'weekly_report' || n.type === 'daily_report')
  if (currentFilter === 'review') return notifications.filter(n => n.type === 'reminder')
  return notifications
}

/**
 * 渲染单个通知项
 */
function renderNotificationItem(n) {
  const icons = {
    'weekly_report': '📊',
    'score_alert': '📈',
    'learning_plan': '📖',
    'reminder': '⏰',
    'daily_report': '✓',
    'warning': '🔴',
    'default': '📢'
  }

  const icon = icons[n.type] || icons.default
  const isUnread = !n.is_read

  return `
    <div class="notification-item ${isUnread ? 'unread' : ''}"
         onclick="studentNotificationsModule.handleClick('${n.notification_id}')">
      <div class="notification-icon">${icon}</div>
      <div class="notification-content">
        <div class="notification-header">
          <span class="notification-type">${getNotificationTypeName(n.type)}</span>
          <span class="notification-time">${formatTime(n.created_at)}</span>
        </div>
        <div class="notification-title">${n.title || ''}</div>
        ${n.content ? `<div class="notification-body">${n.content}</div>` : ''}
      </div>
      ${isUnread ? '<div class="unread-dot"></div>' : ''}
    </div>
  `
}

/**
 * 获取通知类型名称
 */
function getNotificationTypeName(type) {
  const names = {
    'weekly_report': '周报',
    'score_alert': '成绩预警',
    'learning_plan': '学习计划',
    'reminder': '复习提醒',
    'daily_report': '练习报告',
    'warning': '预警'
  }
  return names[type] || '通知'
}

/**
 * 格式化时间
 */
function formatTime(timeStr) {
  if (!timeStr) return ''

  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

/**
 * 处理通知点击
 */
export async function handleNotificationClick(notificationId) {
  try {
    const studentId = getCurrentStudentId()
    await notificationService.markAsRead(notificationId, studentId)

    // 更新本地状态
    const notification = notifications.find(n => n.notification_id === notificationId)
    if (notification) {
      notification.is_read = true
    }

    // 重新渲染
    const container = document.getElementById('notifications-content')
    if (container) {
      renderNotifications(container)
    }

    // 更新未读数
    updateUnreadCount()
  } catch (error) {
    console.error('标记已读失败:', error)
  }
}

/**
 * 加载更多
 */
export async function loadMore() {
  currentPage++
  const container = document.getElementById('notifications-content')
  if (container) {
    await loadNotifications(container, true)
  }
}

/**
 * 切换筛选
 */
export function switchFilter(filter) {
  currentFilter = filter

  // 更新筛选按钮状态
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === filter)
  })

  // 重新渲染
  const container = document.getElementById('notifications-content')
  if (container) {
    renderNotifications(container)
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
 * 更新未读数
 */
function updateUnreadCount() {
  const unreadCount = notifications.filter(n => !n.is_read).length
  const badge = document.getElementById('notifications-unread-badge')
  if (badge) {
    badge.textContent = unreadCount
    badge.style.display = unreadCount > 0 ? 'block' : 'none'
  }
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.studentNotificationsModule = {
    init: initNotificationsModule,
    handleClick: handleNotificationClick,
    loadMore,
    switchFilter
  }
}

export default {
  init: initNotificationsModule,
  handleClick: handleNotificationClick,
  loadMore,
  switchFilter
}
