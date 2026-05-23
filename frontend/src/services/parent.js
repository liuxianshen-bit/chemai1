/**
 * 家长端 API 服务
 */

const API_BASE = ''  // 通过 Vite proxy 转发

/**
 * 家长服务
 */
export const parentService = {
  /**
   * 家长注册
   */
  async register(userData) {
    const response = await fetch(`${API_BASE}/api/parent/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData)
    })
    const data = await response.json()
    return data
  },

  /**
   * 家长登录
   */
  async login(username, password) {
    const response = await fetch(`${API_BASE}/api/parent/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    })
    const data = await response.json()
    if (data.success) {
      // 保存会话
      const session = {
        parent_id: data.parent_id,
        name: data.name,
        role: data.role,
        token: data.token || 'parent_token_' + Date.now()
      }
      sessionStorage.setItem('chemai_user', JSON.stringify(session))
    }
    return data
  },

  /**
   * 获取已绑定子女列表
   */
  async getChildren() {
    const session = getSession()
    if (!session) return { success: false, message: '未登录' }

    const response = await fetch(`${API_BASE}/api/parent/children?parent_id=${session.parent_id}`)
    const data = await response.json()
    return data
  },

  /**
   * 绑定学生
   */
  async bindStudent(studentId, bindCode, relation = '家长') {
    const session = getSession()
    if (!session) return { success: false, message: '未登录' }

    const response = await fetch(`${API_BASE}/api/parent/bind`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: studentId,
        bind_code: bindCode,
        relation: relation,
        parent_id: session.parent_id
      })
    })
    const data = await response.json()
    return data
  },

  /**
   * 解除绑定
   */
  async unbindStudent(bindingId) {
    const session = getSession()
    if (!session) return { success: false, message: '未登录' }

    const response = await fetch(`${API_BASE}/api/parent/bind/${bindingId}?parent_id=${session.parent_id}`, {
      method: 'DELETE'
    })
    const data = await response.json()
    return data
  },

  /**
   * 获取通知列表
   */
  async getNotifications(limit = 20, offset = 0) {
    const session = getSession()
    if (!session) return { success: false, message: '未登录' }

    const response = await fetch(`${API_BASE}/api/parent/notifications?parent_id=${session.parent_id}&limit=${limit}&offset=${offset}`)
    const data = await response.json()
    return data
  },

  /**
   * 标记通知已读
   */
  async markNotificationRead(notificationId) {
    const session = getSession()
    if (!session) return { success: false, message: '未登录' }

    const response = await fetch(`${API_BASE}/api/parent/notifications/${notificationId}/read?parent_id=${session.parent_id}`, {
      method: 'PUT'
    })
    const data = await response.json()
    return data
  },

  /**
   * 获取子女报告摘要
   */
  async getChildReport(studentId) {
    const session = getSession()
    if (!session) return { success: false, message: '未登录' }

    const response = await fetch(`${API_BASE}/api/parent/child/${studentId}/report?parent_id=${session.parent_id}`)
    const data = await response.json()
    return data
  },

  /**
   * 获取子女周报
   */
  async getChildWeekly(studentId) {
    const session = getSession()
    if (!session) return { success: false, message: '未登录' }

    const response = await fetch(`${API_BASE}/api/parent/child/${studentId}/weekly?parent_id=${session.parent_id}`)
    const data = await response.json()
    return data
  },

  /**
   * 生成绑定码（学生在自己的客户端调用）
   */
  async generateBindCode(studentId) {
    const response = await fetch(`${API_BASE}/api/parent/send-bind-code/${studentId}`, {
      method: 'POST'
    })
    const data = await response.json()
    return data
  }
}

/**
 * 获取当前会话
 */
function getSession() {
  const sessionStr = sessionStorage.getItem('chemai_user')
  if (!sessionStr) return null
  try {
    return JSON.parse(sessionStr)
  } catch {
    return null
  }
}

/**
 * 检查是否已登录
 */
export function isLoggedIn() {
  const session = getSession()
  return session !== null && session.role === 'parent'
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser() {
  return getSession()
}

/**
 * 清除会话
 */
export function logout() {
  sessionStorage.removeItem('chemai_user')
  window.location.href = '/login.html'
}
