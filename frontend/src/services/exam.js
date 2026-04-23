/**
 * 考试服务 - Exam Service
 */
import { api } from './api.js'

export const examService = {
  /**
   * 获取班级考试列表
   */
  async getExamList(classId) {
    return await api.get(`/api/exam/list/${classId}`)
  },

  /**
   * 获取考试详情
   */
  async getExamDetail(examId) {
    return await api.get(`/api/exam/${examId}`)
  },

  /**
   * 创建考试
   */
  async createExam(examData) {
    return await api.post('/api/exam/create', examData)
  },

  /**
   * 更新考试
   */
  async updateExam(examId, examData) {
    return await api.put(`/api/exam/${examId}`, examData)
  },

  /**
   * 删除考试
   */
  async deleteExam(examId) {
    return await api.delete(`/api/exam/${examId}`)
  },

  /**
   * 发布考试
   */
  async publishExam(examId) {
    return await api.post(`/api/exam/${examId}/publish`)
  },

  /**
   * 获取学生考试结果
   */
  async getStudentResult(examId, studentId) {
    return await api.get(`/api/exam/${examId}/result/${studentId}`)
  },

  // ==================== 真题集管理 API ====================

  /**
   * 获取真题集列表
   */
  async getExamSets(params = {}) {
    return await api.get('/api/exam-bank/exam-sets', params)
  },

  /**
   * 获取真题集详情
   */
  async getExamSetDetail(setId) {
    return await api.get(`/api/exam-bank/exam-sets/${setId}`)
  },

  /**
   * 创建真题集
   */
  async createExamSet(data) {
    return await api.post('/api/exam-bank/exam-sets', data)
  },

  /**
   * 删除真题集
   */
  async deleteExamSet(setId) {
    return await api.delete(`/api/exam-bank/exam-sets/${setId}`)
  },

  /**
   * 查询历年真题
   */
  async getHistoricalQuestions(params = {}) {
    return await api.get('/api/exam-bank/historical', params)
  },

  /**
   * 格式化OCR文本为题目
   */
  async formatQuestions(rawText, sourceInfo = null) {
    return await api.post('/api/exam-bank/format-questions', {
      raw_text: rawText,
      source_info: sourceInfo
    })
  },

  /**
   * 导入题目到真题集
   */
  async importQuestions(setId, questions) {
    return await api.post('/api/exam-bank/import-questions', {
      set_id: setId,
      questions: questions
    })
  },

  // ==================== 智能文档解析 API ====================

  /**
   * 智能解析文档（自动选择解析方式）
   */
  async smartParseDocument(fileData, fileType = 'auto', source = 'auto') {
    return await api.post('/api/ocr/parse/document', {
      file_data: fileData,
      file_type: fileType,
      source: source
    })
  },

  /**
   * 获取解析服务状态
   */
  async getServicesStatus() {
    return await api.get('/api/ocr/services/status')
  }
}
