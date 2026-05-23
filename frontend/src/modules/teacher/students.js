/**
 * 教师端 - 学生管理模块
 */
import { userService } from '../../services/index.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

// 全局状态
let currentStudentList = []
let currentPendingList = []

/**
 * 初始化学生管理模块
 */
export async function initStudentsModule() {
  const container = document.getElementById('student-list-container')
  if (!container) return

  await loadStudentList()
}

/**
 * 加载学生列表
 */
export async function loadStudentList() {
  const container = document.getElementById('student-list-container')
  if (!container) return

  showLoading('加载学生列表...')

  try {
    // 获取当前教师ID
    const teacherId = getCurrentTeacherId()
    const result = await userService.getTeacherStudents(teacherId)

    if (result.success) {
      currentStudentList = result.data || []
      renderStudentList(currentStudentList)
    } else {
      Toast.error('加载学生列表失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 加载待审核学生
 */
export async function loadPendingStudents() {
  const container = document.getElementById('pending-student-list')
  if (!container) return

  try {
    const teacherId = getCurrentTeacherId()
    const result = await userService.getPendingStudents(teacherId)

    if (result.success) {
      currentPendingList = result.data || []
      renderPendingList(currentPendingList)
      updatePendingBadge(currentPendingList.length)
    }
  } catch (error) {
    console.error('加载待审核学生失败:', error)
  }
}

/**
 * 渲染学生列表
 */
function renderStudentList(students) {
  const container = document.getElementById('student-list-container')
  if (!container) return

  if (students.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-size:3rem;margin-bottom:16px;">👨‍🎓</div>
        <p>暂无学生</p>
      </div>
    `
    return
  }

  container.innerHTML = students.map(student => `
    <div class="student-card" data-id="${student.id}">
      <div class="student-avatar">${(student.name || 'U').charAt(0)}</div>
      <div class="student-info">
        <h4>${student.name || '未知姓名'}</h4>
        <p>${student.username || ''}</p>
        <p class="student-meta">
          ${student.class_name ? `班级: ${student.class_name}` : ''}
          注册时间: ${formatDate(student.created_at)}
        </p>
      </div>
      <div class="student-actions">
        <button class="btn-secondary" onclick="viewStudentReport('${student.id}')">查看报告</button>
        <button class="btn-secondary" onclick="sendPracticeToStudent('${student.id}')">发送练习</button>
      </div>
    </div>
  `).join('')
}

/**
 * 渲染待审核学生列表
 */
function renderPendingList(students) {
  const container = document.getElementById('pending-student-list')
  if (!container) return

  if (students.length === 0) {
    container.innerHTML = '<p class="empty">暂无待审核学生</p>'
    return
  }

  container.innerHTML = students.map(student => `
    <div class="pending-card" data-id="${student.id}">
      <div class="student-avatar">${(student.name || 'U').charAt(0)}</div>
      <div class="student-info">
        <h4>${student.name || '未知姓名'}</h4>
        <p>${student.username || ''}</p>
        <p class="student-meta">申请时间: ${formatDate(student.created_at)}</p>
      </div>
      <div class="student-actions">
        <button class="btn-success" onclick="approveStudent('${student.id}', true)">通过</button>
        <button class="btn-danger" onclick="approveStudent('${student.id}', false)">拒绝</button>
      </div>
    </div>
  `).join('')
}

/**
 * 更新待审核徽章
 */
function updatePendingBadge(count) {
  const badge = document.getElementById('pending-badge')
  if (badge) {
    badge.textContent = count
    badge.style.display = count > 0 ? 'inline' : 'none'
  }
}

/**
 * 审核学生
 */
export async function approveStudent(studentId, approved) {
  showLoading()

  try {
    const result = await userService.approveStudent(studentId, approved)

    if (result.success) {
      Toast.success(approved ? '已通过' : '已拒绝')
      await Promise.all([loadStudentList(), loadPendingStudents()])
    } else {
      Toast.error(result.message || '操作失败')
    }
  } catch (error) {
    Toast.error('操作失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 查看学生报告
 */
export function viewStudentReport(studentId) {
  window.location.href = `/report.html?student_id=${studentId}`
}

/**
 * 发送练习给学生
 */
export function sendPracticeToStudent(studentId) {
  window.location.href = `/practice.html?action=send&student_id=${studentId}`
}

/**
 * 获取当前教师ID
 */
function getCurrentTeacherId() {
  const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
  return user.id
}

/**
 * 格式化日期
 */
function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.approveStudent = approveStudent
  window.viewStudentReport = viewStudentReport
  window.sendPracticeToStudent = sendPracticeToStudent
  window.teacherModule = window.teacherModule || {}
  window.teacherModule.initStudentsModule = initStudentsModule
}
