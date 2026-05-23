/**
 * 预警服务
 * 调用 /api/warning/* 接口
 */

import { api } from './api.js'

export const warningService = {
  /**
   * 获取待处理预警列表
   */
  async getPendingWarnings(teacherId) {
    return api.get(`/api/warning/pending?teacher_id=${teacherId}`)
  },

  /**
   * 获取班级预警汇总
   */
  async getClassWarnings(classId) {
    return api.get(`/api/warning/class/${classId}`)
  },

  /**
   * 获取预警统计
   */
  async getWarningStats(teacherId) {
    return api.get(`/api/warning/stats?teacher_id=${teacherId}`)
  },

  /**
   * 处理预警
   */
  async processWarning(warningId, processedBy, note = null) {
    return api.post(`/api/warning/${warningId}/process`, {
      processed_by: processedBy,
      note
    })
  },

  /**
   * 忽略预警
   */
  async ignoreWarning(warningId, teacherId, reason = '') {
    return api.post(`/api/warning/${warningId}/ignore`, {
      teacher_id: teacherId,
      reason
    })
  },

  /**
   * 获取预警历史
   */
  async getWarningHistory(classId = null, limit = 50, offset = 0) {
    let url = `/api/warning/history?limit=${limit}&offset=${offset}`
    if (classId) url += `&class_id=${classId}`
    return api.get(url)
  },

  /**
   * 发送预警通知
   */
  async sendWarningNotification(warningId, targetType, targetIds) {
    return api.post(`/api/warning/${warningId}/notify`, {
      target_type: targetType,
      target_ids: targetIds
    })
  }
}

export default warningService
