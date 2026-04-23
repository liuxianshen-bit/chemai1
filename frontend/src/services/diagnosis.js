/**
 * 诊断服务 - Diagnosis Service
 */
import { api } from './api.js'

// 障碍类型
export const BarrierType = {
  CONCEPT: 'concept',           // 概念理解型
  READING: 'reading',            // 审题障碍型
  EXPRESSION: 'expression'       // 表述障碍型
}

// 障碍等级
export const BarrierLevel = {
  MILD: 'mild',                 // 轻度
  MODERATE: 'moderate',         // 中度
  SEVERE: 'severe'              // 重度
}

// 障碍类型名称映射
export const BarrierTypeNames = {
  [BarrierType.CONCEPT]: '概念理解型',
  [BarrierType.READING]: '审题障碍型',
  [BarrierType.EXPRESSION]: '表述障碍型'
}

// 障碍等级名称映射
export const BarrierLevelNames = {
  [BarrierLevel.MILD]: '轻度',
  [BarrierLevel.MODERATE]: '中度',
  [BarrierLevel.SEVERE]: '重度'
}

export const diagnosisService = {
  /**
   * 获取班级障碍诊断
   */
  async getBarrierDiagnosis(classId, examId) {
    return await api.get(`/api/diagnosis/barrier/${classId}/${examId}`)
  },

  /**
   * 获取学生障碍诊断
   */
  async getStudentDiagnosis(studentId) {
    return await api.get(`/api/diagnosis/student/${studentId}`)
  },

  /**
   * 获取干预方案
   */
  async getInterventionPlan(studentId) {
    return await api.get(`/api/diagnosis/plan/${studentId}`)
  },

  /**
   * 提交障碍反馈
   */
  async submitFeedback(diagnosisId, feedback) {
    return await api.post(`/api/diagnosis/${diagnosisId}/feedback`, feedback)
  },

  /**
   * 获取诊断历史
   */
  async getDiagnosisHistory(studentId, params = {}) {
    return await api.get(`/api/diagnosis/history/${studentId}`, params)
  },

  /**
   * 获取班级障碍分布统计
   */
  async getClassBarrierStats(classId) {
    return await api.get(`/api/diagnosis/class/${classId}/stats`)
  },

  /**
   * 获取知识点障碍分析
   */
  async getKPBarnerAnalysis(classId, knowledgePoint) {
    return await api.get(`/api/diagnosis/class/${classId}/kp/${knowledgePoint}`)
  },

  // ============================================
  // 学习计划相关
  // ============================================

  /**
   * 生成学生学习计划
   * @param {string} studentId - 学生ID
   * @param {object} params - { barrier_type, weak_knowledge_points, recent_performance }
   */
  async generateLearningPlan(studentId, params) {
    return await api.post('/api/diagnosis/learning-plan/generate', {
      student_id: studentId,
      ...params
    })
  },

  /**
   * 应用学习计划到学生
   */
  async applyLearningPlan(studentId, planData) {
    return await api.post(`/api/diagnosis/learning-plan/apply/${studentId}`, planData)
  },

  /**
   * 发送学习计划给家长
   */
  async sendPlanToParent(studentId) {
    return await api.post(`/api/diagnosis/learning-plan/send-to-parent/${studentId}`)
  },

  /**
   * 获取学生当前学习计划
   */
  async getStudentLearningPlan(studentId) {
    return await api.get(`/api/diagnosis/learning-plan/${studentId}`)
  }
}
