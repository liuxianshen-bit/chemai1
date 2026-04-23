/**
 * 题目服务 - Question Service
 */
import { api } from './api.js'

export const questionService = {
  /**
   * AI生成题目
   */
  async generate(params) {
    return await api.post('/api/question/generate', params)
  },

  /**
   * 审核题目
   */
  async audit(questionContent, options = null) {
    const body = { question_content: questionContent }
    if (options) body.options = options
    return await api.post('/api/question/audit', body)
  },

  /**
   * 获取历史真题
   */
  async getHistorical(params = {}) {
    return await api.get('/api/question/historical', params)
  },

  /**
   * 查找相似题
   */
  async findSimilar(questionId) {
    return await api.get(`/api/question/similar/${questionId}`)
  },

  /**
   * 搜索题目
   */
  async search(params) {
    return await api.post('/api/question/search', params)
  },

  /**
   * 获取题目详情
   */
  async getDetail(questionId) {
    return await api.get(`/api/question/${questionId}`)
  },

  /**
   * 审核题目（通过）
   */
  async approve(questionId) {
    return await api.post(`/api/question/${questionId}/approve`)
  },

  /**
   * 审核题目（拒绝）
   */
  async reject(questionId, reason) {
    return await api.post(`/api/question/${questionId}/reject`, { reason })
  },

  /**
   * 获取题库分类
   */
  async getCategories() {
    return await api.get('/api/question/categories')
  },

  /**
   * 获取知识点列表
   */
  async getKnowledgePoints() {
    return await api.get('/api/question/kps')
  }
}
