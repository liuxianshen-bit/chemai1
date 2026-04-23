/**
 * 用户服务 - User Service
 */
import { api } from './api.js'
import { authService, UserStatus } from './auth.js'

// ============================================
// 用户服务
// ============================================
export const userService = {
  /**
   * 获取用户列表 (管理员)
   */
  async getUserList(params = {}) {
    return await api.get('/api/user/list', params)
  },

  /**
   * 获取用户详情
   */
  async getUserDetail(userId) {
    return await api.get(`/api/user/${userId}`)
  },

  /**
   * 更新用户信息
   */
  async updateUser(userId, userData) {
    return await api.put(`/api/user/${userId}`, userData)
  },

  /**
   * 删除用户 (管理员)
   */
  async deleteUser(userId) {
    return await api.delete(`/api/user/${userId}`)
  },

  // ============================================
  // 教师专用方法
  // ============================================

  /**
   * 获取待审核学生列表 (教师)
   */
  async getPendingStudents(teacherId) {
    return await api.get(`/api/user/teacher/${teacherId}/pending-students`)
  },

  /**
   * 审核学生 (教师)
   */
  async approveStudent(studentId, approved) {
    return await api.post(`/api/user/student/${studentId}/approve`, { approved })
  },

  /**
   * 获取教师的学生列表
   */
  async getTeacherStudents(teacherId) {
    return await api.get(`/api/user/teacher/${teacherId}/students`)
  },

  /**
   * 获取教师的任教班级列表
   */
  async getTeacherClasses(teacherId) {
    return await api.get(`/api/users/teacher/${teacherId}/classes`)
  },

  // ============================================
  // 管理员专用方法
  // ============================================

  /**
   * 获取待审核教师列表 (管理员)
   */
  async getPendingTeachers() {
    return await api.get('/api/user/admin/pending-teachers')
  },

  /**
   * 审核教师 (管理员)
   */
  async approveTeacher(teacherId, approved) {
    return await api.post(`/api/user/teacher/${teacherId}/approve`, { approved })
  },

  /**
   * 获取教师列表 (管理员)
   */
  async getTeacherList() {
    return await api.get('/api/user/admin/teachers')
  },

  // ============================================
  // 学生设置方法
  // ============================================

  /**
   * 获取用户设置
   */
  async getUserSettings() {
    return await api.get('/api/user/settings')
  },

  /**
   * 更新用户设置
   */
  async updateUserSettings(settings) {
    return await api.put('/api/user/settings', settings)
  },

  /**
   * 修改密码
   */
  async changePassword(oldPassword, newPassword) {
    return await api.post('/api/user/change-password', {
      old_password: oldPassword,
      new_password: newPassword
    })
  }
}

// ============================================
// 权限服务
// ============================================
export const permissionService = {
  // 角色权限定义
  permissions: {
    admin: {
      pages: ['home', 'exam', 'question', 'report', 'diagnosis', 'panel', 'teachers', 'students', 'classes', 'grade', 'ocr', 'teacher-apps'],
      actions: [
        'manage_teachers', 'manage_students', 'manage_classes', 'manage_grades',
        'create_exam', 'generate_questions', 'audit_questions',
        'view_reports', 'configure_diagnosis', 'send_to_students',
        'import_questions', 'manage_exam_bank', 'approve_teachers'
      ]
    },
    '教务管理员': {
      pages: ['home', 'exam', 'question', 'report', 'diagnosis', 'panel', 'students', 'classes', 'grade', 'ocr'],
      actions: [
        'manage_students', 'manage_classes', 'manage_grades',
        'create_exam', 'generate_questions', 'audit_questions',
        'view_reports', 'configure_diagnosis', 'send_to_students',
        'import_questions', 'manage_exam_bank'
      ]
    },
    '学科组长': {
      pages: ['home', 'exam', 'question', 'report', 'diagnosis', 'panel', 'ocr'],
      actions: [
        'create_exam', 'generate_questions', 'audit_questions',
        'view_reports', 'configure_diagnosis', 'send_to_students',
        'view_students', 'approve_students', 'import_questions'
      ]
    },
    teacher: {
      pages: ['home', 'exam', 'question', 'report', 'diagnosis', 'panel', 'students', 'ocr'],
      actions: [
        'create_exam', 'generate_questions', 'audit_questions',
        'view_reports', 'configure_diagnosis', 'send_to_students',
        'view_students', 'approve_students', 'import_questions'
      ]
    },
    student: {
      pages: ['home', 'practice', 'wrong', 'report', 'profile'],
      actions: ['view_tasks', 'submit_practice', 'view_wrong', 'view_profile']
    }
  },

  /**
   * 检查是否有页面访问权限
   */
  canAccessPage(pageName) {
    const user = authService.getCurrentUserFromSession()
    if (!user) return false
    if (user.role === 'admin') return true
    const rolePerms = this.permissions[user.role]
    if (!rolePerms) return false
    return rolePerms.pages.includes(pageName)
  },

  /**
   * 检查是否有操作权限
   */
  canDo(action) {
    const user = authService.getCurrentUserFromSession()
    if (!user) return false
    if (user.role === 'admin') return true
    const rolePerms = this.permissions[user.role]
    if (!rolePerms) return false
    return rolePerms.actions.includes(action)
  },

  /**
   * 检查是否可以管理指定学生
   */
  canManageStudent(studentId) {
    const user = authService.getCurrentUserFromSession()
    if (!user) return false
    if (user.role === 'admin' || user.role === '教务管理员') return true
    if (user.role === 'teacher' || user.role === '学科组长') {
      // 需要检查学生是否属于该教师
      return true // TODO: 调用API验证
    }
    return false
  },

  /**
   * 获取用户可访问的页面
   */
  getAccessiblePages() {
    const user = authService.getCurrentUserFromSession()
    if (!user) return []
    if (user.role === 'admin') return this.permissions.admin.pages
    return this.permissions[user.role]?.pages || []
  }
}

// ============================================
// 班级服务
// ============================================
export const classService = {
  /**
   * 获取班级列表
   */
  async getClassList() {
    return await api.get('/api/classes')
  },

  /**
   * 获取班级详情
   */
  async getClassDetail(classId) {
    return await api.get(`/api/classes/${classId}`)
  },

  /**
   * 获取班级的学生
   */
  async getClassStudents(classId) {
    return await api.get(`/api/classes/${classId}/students`)
  },

  /**
   * 创建班级 (管理员)
   */
  async createClass(classData) {
    return await api.post('/api/classes', classData)
  },

  /**
   * 更新班级
   */
  async updateClass(classId, classData) {
    return await api.put(`/api/classes/${classId}`, classData)
  },

  /**
   * 删除班级 (管理员)
   */
  async deleteClass(classId) {
    return await api.delete(`/api/classes/${classId}`)
  }
}
