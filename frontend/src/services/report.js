/**
 * 报告服务 - Report Service
 */
import { api } from './api.js'

export const reportService = {
  /**
   * 获取学生练习报告
   */
  async getStudentReport(studentId, params = {}) {
    return await api.get(`/api/report/student/${studentId}`, params)
  },

  /**
   * 获取班级学情报告
   */
  async getClassReport(classId, params = {}) {
    return await api.get(`/api/report/class/${classId}`, params)
  },

  /**
   * 获取教师教学报告
   */
  async getTeacherReport(teacherId, params = {}) {
    return await api.get(`/api/report/teacher/${teacherId}`, params)
  },

  /**
   * 获取知识点掌握报告
   */
  async getKPMasteryReport(studentId) {
    return await api.get(`/api/report/student/${studentId}/kp-mastery`)
  },

  /**
   * 获取障碍变化报告
   */
  async getBarrierChangeReport(studentId, params = {}) {
    return await api.get(`/api/report/student/${studentId}/barrier-change`, params)
  },

  /**
   * 获取学习趋势报告
   */
  async getLearningTrendReport(studentId, params = {}) {
    return await api.get(`/api/report/student/${studentId}/trend`, params)
  },

  /**
   * 导出报告
   */
  async exportReport(reportType, params = {}) {
    return await api.get(`/api/report/export/${reportType}`, params)
  }
}
