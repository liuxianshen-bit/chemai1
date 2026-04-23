/**
 * 学校/年级/教师入驻服务
 */
import { api } from './api.js'

// ============================================
// 学校服务
// ============================================
export const schoolService = {
  /**
   * 获取学校信息
   */
  async getSchool() {
    return await api.get('/api/school')
  },

  /**
   * 更新学校信息（管理员）
   */
  async updateSchool(schoolData) {
    return await api.put('/api/school', schoolData)
  }
}

// ============================================
// 年级服务
// ============================================
export const gradeService = {
  /**
   * 获取年级列表
   */
  async getGrades() {
    return await api.get('/api/grades')
  },

  /**
   * 创建年级（管理员）
   */
  async createGrade(gradeData) {
    return await api.post('/api/grades', gradeData)
  },

  /**
   * 更新年级
   */
  async updateGrade(gradeId, gradeData) {
    return await api.put(`/api/grades/${gradeId}`, gradeData)
  },

  /**
   * 删除年级（管理员）
   */
  async deleteGrade(gradeId) {
    return await api.delete(`/api/grades/${gradeId}`)
  }
}

// ============================================
// 教师入驻申请服务
// ============================================
export const teacherAppService = {
  /**
   * 获取入驻申请列表（管理员）
   */
  async getApplications(status = null) {
    const params = status ? { status } : {}
    return await api.get('/api/teacher-applications', params)
  },

  /**
   * 审批通过申请（管理员）
   */
  async approveApplication(appId) {
    return await api.post(`/api/teacher-applications/${appId}/approve`)
  },

  /**
   * 审批拒绝申请（管理员）
   */
  async rejectApplication(appId, reason = '') {
    return await api.post(`/api/teacher-applications/${appId}/reject`, { reason })
  }
}
