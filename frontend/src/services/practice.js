/**
 * 练习服务 - Practice Service
 */
import { api } from './api.js'

// 练习状态
export const PracticeStatus = {
  PENDING: 'pending',           // 待完成
  COMPLETED: 'completed',       // 已完成
  OVERDUE: 'overdue'            // 已逾期
}

// 练习状态名称映射
export const PracticeStatusNames = {
  [PracticeStatus.PENDING]: '待完成',
  [PracticeStatus.COMPLETED]: '已完成',
  [PracticeStatus.OVERDUE]: '已逾期'
}

export const practiceService = {
  /**
   * 获取学生练习任务列表
   */
  async getStudentTasks(studentId) {
    return await api.get(`/api/practice/student/${studentId}/tasks`)
  },

  /**
   * 获取练习题目
   */
  async getPracticeQuestions(practiceId) {
    return await api.get(`/api/practice/${practiceId}/questions`)
  },

  /**
   * 提交练习答案
   */
  async submitPractice(practiceId, answers) {
    return await api.post('/api/practice/submit', {
      practice_id: practiceId,
      answers: answers
    })
  },

  /**
   * 获取练习效果
   */
  async getPracticeEffect(studentId) {
    return await api.get(`/api/practice/effect/${studentId}`)
  },

  /**
   * 教师布置练习
   */
  async assignPractice(requestData) {
    return await api.post('/api/practice/assign', requestData)
  },

  /**
   * 获取学生练习历史
   */
  async getPracticeHistory(studentId, params = {}) {
    return await api.get(`/api/practice/history/${studentId}`, params)
  },

  /**
   * 获取错题列表
   */
  async getWrongQuestions() {
    return await api.get('/api/practice/wrong/list')
  },

  /**
   * 标记错题已掌握
   */
  async markAsMastered(questionId) {
    return await api.post(`/api/practice/wrong/${questionId}/master`)
  },

  /**
   * 获取待复习错题
   */
  async getReviewQuestions() {
    return await api.get('/api/practice/review/list')
  },

  /**
   * 获取历史真题
   */
  async getHistoricalQuestions(params = {}) {
    return await api.get('/api/practice/historical', params)
  }
}

// 复习服务 - Review Service
export const reviewService = {
  /**
   * 获取到期复习任务
   */
  async getDueReviews(studentId) {
    return await api.get(`/api/review/student/${studentId}/due`)
  },

  /**
   * 获取待复习数量
   */
  async getReviewCount(studentId) {
    return await api.get(`/api/review/student/${studentId}/count`)
  },

  /**
   * 提交复习结果
   */
  async submitReview(taskId, isCorrect) {
    return await api.post('/api/review/submit', {
      task_id: taskId,
      is_correct: isCorrect
    })
  },

  /**
   * 同步复习任务
   */
  async syncReviewTasks(studentId) {
    return await api.post(`/api/review/sync/${studentId}`)
  },

  /**
   * 获取复习历史
   */
  async getReviewHistory(studentId, limit = 20) {
    return await api.get(`/api/review/history/${studentId}?limit=${limit}`)
  }
}
