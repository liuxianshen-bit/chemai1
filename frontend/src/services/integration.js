/**
 * LMS集成服务
 * 调用 /api/integration/* 接口
 */

import { api } from './api.js'

export const integrationService = {
  /**
   * 获取LMS配置
   */
  async getLmsConfig() {
    return api.get('/api/integration/lms/config')
  },

  /**
   * 保存LMS配置
   */
  async saveLmsConfig(config) {
    return api.post('/api/integration/lms/config', config)
  },

  /**
   * 测试LMS连接
   */
  async testLmsConnection(platform, config) {
    return api.post('/api/integration/lms/test', { platform, config })
  },

  /**
   * 获取Webhook列表
   */
  async getWebhooks() {
    return api.get('/api/integration/webhooks')
  },

  /**
   * 注册Webhook
   */
  async registerWebhook(eventType, url, secret = '') {
    return api.post('/api/integration/webhooks', {
      event_type: eventType,
      url,
      secret
    })
  },

  /**
   * 删除Webhook
   */
  async unregisterWebhook(eventType) {
    return api.delete(`/api/integration/webhooks/${eventType}`)
  },

  /**
   * 测试Webhook
   */
  async testWebhook(eventType, url, secret = '') {
    return api.post('/api/integration/webhooks/test', { event_type: eventType, url, secret })
  },

  /**
   * 获取API密钥列表
   */
  async getApiKeys() {
    return api.get('/api/integration/api-keys')
  },

  /**
   * 创建API密钥
   */
  async createApiKey(name, permissions) {
    return api.post('/api/integration/api-keys', { name, permissions })
  },

  /**
   * 删除API密钥
   */
  async deleteApiKey(keyId) {
    return api.delete(`/api/integration/api-keys/${keyId}`)
  },

  /**
   * 获取SFTP配置
   */
  async getSftpConfig() {
    return api.get('/api/integration/sftp/config')
  },

  /**
   * 保存SFTP配置
   */
  async saveSftpConfig(config) {
    return api.post('/api/integration/sftp/config', config)
  },

  /**
   * 测试SFTP连接
   */
  async testSftpConnection(config) {
    return api.post('/api/integration/sftp/test', config)
  },

  /**
   * 获取集成日志
   */
  async getIntegrationLogs(eventType = null, platform = null, status = null, limit = 50) {
    let url = `/api/integration/logs?limit=${limit}`
    if (eventType) url += `&event_type=${eventType}`
    if (platform) url += `&platform=${platform}`
    if (status) url += `&status=${status}`
    return api.get(url)
  }
}

export default integrationService
