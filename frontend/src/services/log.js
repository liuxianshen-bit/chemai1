/**
 * 日志服务
 * 调用 /api/logs 接口
 */

import { api } from './api.js'

export const logService = {
  /**
   * 获取日志列表
   * @param {Object} params - 查询参数
   * @param {string} params.action - 操作类型
   * @param {string} params.target_type - 目标类型
   * @param {string} params.user_id - 用户ID
   * @param {number} params.days - 查询天数，默认7
   */
  async getLogs(params = {}) {
    let url = '/api/logs?'
    if (params.action) url += `action=${params.action}&`
    if (params.target_type) url += `target_type=${params.target_type}&`
    if (params.user_id) url += `user_id=${params.user_id}&`
    if (params.days) url += `days=${params.days}&`
    return api.get(url)
  },

  /**
   * 获取操作类型枚举
   */
  async getLogTypes() {
    // 预定义的操作类型
    return {
      success: true,
      types: [
        { value: 'login', label: '登录' },
        { value: 'logout', label: '登出' },
        { value: 'create', label: '创建' },
        { value: 'update', label: '更新' },
        { value: 'delete', label: '删除' },
        { value: 'ocr', label: 'OCR识别' },
        { value: 'exam_create', label: '创建考试' },
        { value: 'exam_submit', label: '提交考试' },
        { value: 'warning', label: '预警' },
        { value: 'notification', label: '通知' },
        { value: 'report', label: '报告' }
      ]
    }
  }
}

export default logService
