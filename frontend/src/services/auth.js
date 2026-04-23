/**
 * 认证服务 - Auth Service
 */
import { api, handleApiError } from './api.js'

// 用户状态常量
export const UserStatus = {
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected'
}

// 角色常量
export const UserRole = {
  ADMIN: 'admin',
  TEACHER: 'teacher',
  STUDENT: 'student'
}

// ============================================
// 认证服务
// ============================================
export const authService = {
  /**
   * 用户登录
   */
  async login(username, password) {
    try {
      const data = await api.post('/api/auth/login', { username, password })
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  },

  /**
   * 用户注册
   */
  async register(userData) {
    try {
      const data = await api.post('/api/auth/register', userData)
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  },

  /**
   * 登出
   */
  async logout() {
    try {
      await api.post('/api/auth/logout')
    } catch (error) {
      console.warn('Logout API failed:', error)
    }
  },

  /**
   * 获取当前用户信息
   */
  async getCurrentUser() {
    try {
      const data = await api.get('/api/auth/me')
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  },

  /**
   * 检查登录状态
   */
  isLoggedIn() {
    const session = sessionStorage.getItem('chemai_user')
    if (!session) return false
    const user = JSON.parse(session)
    return user && user.status === UserStatus.APPROVED
  },

  /**
   * 获取当前用户
   */
  getCurrentUserFromSession() {
    const session = sessionStorage.getItem('chemai_user')
    return session ? JSON.parse(session) : null
  },

  /**
   * 保存用户会话
   */
  saveSession(user, token = null, refreshToken = null) {
    const session = {
      id: user.id,
      username: user.username || user.account,
      role: user.role,
      status: user.status,
      name: user.name,
      school: user.school,
      classId: user.classId,
      classIds: user.classIds,
      teacherId: user.teacherId,
      token: token,
      refreshToken: refreshToken,
      loginTime: new Date().toISOString()
    }
    sessionStorage.setItem('chemai_user', JSON.stringify(session))
    return session
  },

  /**
   * 教师入驻申请
   */
  async teacherApply(applyData) {
    try {
      const data = await api.post('/api/auth/apply', applyData)
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  },

  /**
   * 清除会话
   */
  clearSession() {
    sessionStorage.removeItem('chemai_user')
  },

  /**
   * 检查是否是管理员
   */
  isAdmin() {
    const user = this.getCurrentUserFromSession()
    return user && user.role === UserRole.ADMIN
  },

  /**
   * 检查是否是教师
   */
  isTeacher() {
    const user = this.getCurrentUserFromSession()
    return user && user.role === UserRole.TEACHER
  },

  /**
   * 检查是否是学生
   */
  isStudent() {
    const user = this.getCurrentUserFromSession()
    return user && user.role === UserRole.STUDENT
  }
}
