/**
 * 家长端 - 消息模块
 * 显示通知列表
 */

import { parentService } from '../../services/parent.js'

let notifications = []
let currentPage = 0
const pageSize = 20

export async function initParentNotifications() {
  const container = document.getElementById('notifications-content')
  if (!container) return

  currentPage = 0
  notifications = []
  await loadNotifications(container)
}

async function loadNotifications(container, append = false) {
  if (!append) {
    container.innerHTML = '<div class="loading-state"><p>加载中...</p></div>'
  }

  try {
    const result = await parentService.getNotifications(pageSize, currentPage * pageSize)

    if (result.success) {
      if (append) {
        notifications = [...notifications, ...result.notifications]
      } else {
        notifications = result.notifications
      }

      if (notifications.length > 0) {
        renderNotifications(container)
      } else {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔔</div><p>暂无通知</p></div>'
      }
    } else {
      container.innerHTML = '<div class="empty-state"><p>加载失败</p></div>'
    }
  } catch (error) {
    console.error('加载通知失败:', error)
    container.innerHTML = '<div class="empty-state"><p>加载失败，请重试</p></div>'
  }
}

function renderNotifications(container) {
  const typeIcons = {
    'weekly_report': '📊',
    'score_alert': '📈',
    'learning_plan': '📖',
    'reminder': '⏰',
    'daily_report': '✓'
  }

  const typeNames = {
    'weekly_report': '周报',
    'score_alert': '成绩预警',
    'learning_plan': '学习计划',
    'reminder': '提醒',
    'daily_report': '练习报告'
  }

  container.innerHTML = `
    <div class="notifications-list">
      ${notifications.map(n => `
        <div class="notification-item ${n.is_read ? '' : 'unread'}" onclick="parentModule.markNotificationRead('${n.notification_id}')">
          <div class="notification-icon">${typeIcons[n.type] || '📢'}</div>
          <div class="notification-content">
            <div class="notification-header">
              <span class="notification-type">${typeNames[n.type] || n.type}</span>
              <span class="notification-student">${n.student_name}</span>
              <span class="notification-time">${formatTime(n.created_at)}</span>
            </div>
            <div class="notification-title">${n.title}</div>
            ${n.content ? `<div class="notification-body">${n.content}</div>` : ''}
          </div>
          ${!n.is_read ? '<div class="unread-dot"></div>' : ''}
        </div>
      `).join('')}
    </div>
  `

  // 如果还有更多数据，显示加载更多
  if (notifications.length >= pageSize) {
    container.innerHTML += `
      <div class="load-more" onclick="parentModule.loadMoreNotifications()">
        加载更多
      </div>
    `
  }
}

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

export async function markNotificationRead(notificationId) {
  try {
    await parentService.markNotificationRead(notificationId)

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
  } catch (error) {
    console.error('标记已读失败:', error)
  }
}

export async function loadMore() {
  currentPage++
  const container = document.getElementById('notifications-content')
  if (container) {
    await loadNotifications(container, true)
  }
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.parentModule = window.parentModule || {}
  window.parentModule.initParentNotifications = initParentNotifications
  window.parentModule.markNotificationRead = markNotificationRead
  window.parentModule.loadMoreNotifications = loadMore
}
