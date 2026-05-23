/**
 * 通知服务
 * 调用 /api/notification/* 接口
 */

import { api } from './api.js'

const API_BASE = ''

export const notificationService = {
  /**
   * 获取学生的通知列表
   */
  async getStudentNotifications(studentId, limit = 20, offset = 0) {
    return api.get(`/api/notification/student/${studentId}/notifications?limit=${limit}&offset=${offset}`)
  },

  /**
   * 标记通知为已读
   */
  async markAsRead(notificationId, studentId) {
    return api.put(`/api/notification/${notificationId}/read?student_id=${studentId}`)
  },

  /**
   * 删除通知
   */
  async deleteNotification(notificationId) {
    return api.delete(`/api/notification/${notificationId}`)
  },

  /**
   * 获取通知历史（教师端）
   */
  async getHistory(targetType = null, notificationType = null, limit = 50, offset = 0) {
    const params = { limit, offset }
    if (targetType) params.target_type = targetType
    if (notificationType) params.notification_type = notificationType
    return api.get('/api/notification/history', params)
  },

  /**
   * 发送通知
   */
  async sendNotification(data) {
    return api.post('/api/notification/send', data)
  },

  /**
   * 发送通知给单个学生
   */
  async sendToStudent(studentId, notificationType, title, content) {
    return api.post(`/api/notification/send-to-student/${studentId}`, {
      notification_type: notificationType,
      title,
      content
    })
  },

  /**
   * 发送通知给学生家长
   */
  async sendToParent(studentId, notificationType, title, content) {
    return api.post(`/api/notification/send-to-parent/${studentId}`, {
      notification_type: notificationType,
      title,
      content
    })
  },

  /**
   * 发送通知给班级
   */
  async sendToClass(classId, notificationType, title, content, target = 'students') {
    return api.post(`/api/notification/send-to-class/${classId}`, {
      notification_type: notificationType,
      title,
      content,
      target
    })
  },

  /**
   * 获取可用渠道
   */
  async getChannels() {
    const response = await fetch(`${API_BASE}/api/notification/channels`)
    return response.json()
  },

  /**
   * 测试Telegram渠道
   */
  async testTelegram(chatId, message = 'ChemAI测试消息') {
    return api.post('/api/notification/test-telegram', { chat_id: chatId, message })
  },

  /**
   * 订阅通知渠道
   */
  async subscribe(userId, userType, channel, channelId) {
    return api.post('/api/notification/subscribe', {
      user_id: userId,
      user_type: userType,
      channel,
      channel_id: channelId
    })
  },

  /**
   * 取消订阅
   */
  async unsubscribe(userId, userType, channel) {
    return api.delete('/api/notification/unsubscribe', {
      body: { user_id: userId, user_type: userType, channel }
    })
  }
}

export default notificationService
