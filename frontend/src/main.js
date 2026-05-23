/**
 * ChemAI Frontend - Main Entry
 */
import { authService } from './services/index.js'
import { Toast } from './components/index.js'

// 学生端模块 - 初始化 window.studentNotificationsModule
import './modules/student/notifications.js'
import './modules/student/wrong.js'
import './modules/student/settings.js'
import './modules/student/report.js'
import './modules/student/learning_plan.js'
import './modules/student/review_center.js'

// 获取已设置的window模块
const studentNotificationsModule = window.studentNotificationsModule || {}
const reviewCenterModule = window.reviewCenterModule || {}

// 教师端模块 - 初始化 window.teacherModule 和其他模块
import './modules/teacher/ocr.js'
import './modules/teacher/exam.js'
import './modules/teacher/students.js'
import './modules/teacher/question.js'
import './modules/teacher/diagnosis.js'
import './modules/teacher/report.js'
import './modules/teacher/panel.js'
import './modules/teacher/admin.js'
import './modules/teacher/warnings.js'
import './modules/teacher/notification.js'
import './modules/teacher/integration.js'
import './modules/teacher/logs.js'

// 获取已设置的window模块
const teacherModule = window.teacherModule || {}
const studentModule = window.studentModule || {}
const teacherNotificationModule = window.teacherNotificationModule || {}

// 页面初始化映射
const pageInitializers = {
  'home': initHomePage,
  'login': initLoginPage,
  'teacher': initTeacherPage,
  'student': initStudentPage,
  'agent': initAgentPage
}

async function initAgentPage() {
  const { initAgentPage: init } = await import('../modules/agent/index.js')
  init()
}

/**
 * 路由初始化
 */
function initHomePage() {
  const user = authService.getCurrentUserFromSession()
  if (!user) {
    window.location.href = '/login.html'
    return
  }
  console.log('Home page initialized for:', user.role)
}

/**
 * 登录页初始化
 */
function initLoginPage() {
  const form = document.getElementById('login-form')
  if (form) {
    form.addEventListener('submit', handleLogin)
  }
}

async function handleLogin(e) {
  e.preventDefault()

  const username = document.getElementById('username')?.value?.trim()
  const password = document.getElementById('password')?.value

  if (!username || !password) {
    Toast.error('请输入用户名和密码')
    return
  }

  try {
    Toast.info('登录中...')
    const result = await authService.login(username, password)

    if (result.success && result.data) {
      const user = result.data.user
      const token = result.data.token
      const refreshToken = result.data.refresh_token
      authService.saveSession(user, token, refreshToken)
      Toast.success('登录成功')
      setTimeout(() => {
        window.location.href = user.role === 'student' ? '/student_v2.html' : '/teacher_v2.html'
      }, 500)
    } else {
      Toast.error(result.message || result.error || '登录失败')
    }
  } catch (error) {
    Toast.error('登录失败：' + error.message)
  }
}

/**
 * 教师页初始化
 */
function initTeacherPage() {
  // 初始化用户信息
  initTeacherUser()

  // 动态菜单（根据角色）
  initDynamicMenu()

  // 初始化OCR上传
  teacherModule.initOcrUpload()

  // 初始化考试模块
  teacherModule.initExamModule()

  // 初始化学生模块
  teacherModule.initStudentsModule()

  // 初始化题目模块
  teacherModule.initQuestionModule()

  // 初始化诊断模块
  teacherModule.initDiagnosisModule()

  // 初始化报告模块
  teacherModule.initReportModule()

  // 初始化面板模块
  teacherModule.initPanelModule()

  // 初始化管理模块（admin专用）
  if (teacherModule.initAdminModule) {
    teacherModule.initAdminModule()
  }

  console.log('Teacher page initialized')
}

/**
 * 动态菜单 - 根据角色显示不同菜单
 */
function initDynamicMenu() {
  const user = authService.getCurrentUserFromSession()
  if (!user) return

  const role = user.role
  const navContainer = document.getElementById('sidebar-nav')
  if (!navContainer) return

  // 菜单配置
  const menuConfig = {
    admin: [
      { page: 'home', label: '首页', icon: 'home' },
      { page: 'school', label: '学校设置', icon: 'school' },
      { page: 'grade', label: '年级管理', icon: 'grade' },
      { page: 'classes', label: '班级管理', icon: 'class' },
      { page: 'teachers', label: '教师管理', icon: 'teacher' },
      { page: 'students', label: '学生管理', icon: 'student' },
      { page: 'ocr', label: '答题卡识别', icon: 'ocr' },
      { page: 'exam', label: '考试管理', icon: 'exam' },
      { page: 'panel', label: '学情面板', icon: 'panel' },
      { page: 'teacher-apps', label: '入驻审批', icon: 'app' },
    ],
    教务管理员: [
      { page: 'home', label: '首页', icon: 'home' },
      { page: 'grade', label: '年级管理', icon: 'grade' },
      { page: 'classes', label: '班级管理', icon: 'class' },
      { page: 'students', label: '学生管理', icon: 'student' },
      { page: 'ocr', label: '答题卡识别', icon: 'ocr' },
      { page: 'exam', label: '考试管理', icon: 'exam' },
      { page: 'panel', label: '学情面板', icon: 'panel' },
    ],
    学科组长: [
      { page: 'home', label: '首页', icon: 'home' },
      { page: 'ocr', label: '答题卡识别', icon: 'ocr' },
      { page: 'exam', label: '考试管理', icon: 'exam' },
      { page: 'panel', label: '学情面板', icon: 'panel' },
    ],
    teacher: [
      { page: 'home', label: '首页', icon: 'home' },
      { page: 'ocr', label: '答题卡识别', icon: 'ocr' },
      { page: 'exam', label: '考试管理', icon: 'exam' },
      { page: 'question', label: '题目管理', icon: 'question' },
      { page: 'diagnosis', label: '障碍诊断', icon: 'diagnosis' },
      { page: 'report', label: '学情报告', icon: 'report' },
      { page: 'students', label: '学生管理', icon: 'student' },
      { page: 'panel', label: '学情面板', icon: 'panel' },
    ]
  }

  const menus = menuConfig[role] || menuConfig.teacher

  // SVG图标映射
  const icons = {
    home: '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="16" width="7" height="5"/>',
    school: '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    grade: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/>',
    class: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
    teacher: '<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    student: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>',
    ocr: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
    exam: '<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/>',
    panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
    app: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/>',
    question: '<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><circle cx="12" cy="14" r="3"/>',
    diagnosis: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    report: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>'
  }

  // 获取当前页面
  const currentPage = window.location.pathname.split('/').pop().replace('.html', '') || 'home'

  // 生成菜单HTML
  navContainer.innerHTML = menus.map(menu => {
    const isActive = menu.page === currentPage ? 'active' : ''
    return `
      <button class="sidebar-nav-item ${isActive}" data-page="${menu.page}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${icons[menu.icon] || icons.home}</svg>
        <span>${menu.label}</span>
      </button>
    `
  }).join('')

  // 绑定导航事件
  navContainer.querySelectorAll('.sidebar-nav-item').forEach(btn => {
    btn.addEventListener('click', function() {
      const targetPage = this.getAttribute('data-page')
      document.querySelectorAll('.sidebar-nav-item').forEach(b => b.classList.remove('active'))
      this.classList.add('active')
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))

      // OCR页面特殊处理：显示首页并聚焦上传区域
      if (targetPage === 'ocr') {
        const homeSection = document.getElementById('page-home')
        if (homeSection) {
          homeSection.classList.add('active')
          // 滚动到上传区域
          const uploadZone = document.getElementById('upload-zone')
          uploadZone?.scrollIntoView({ behavior: 'smooth', block: 'center' })
          // 初始化OCR上传功能
          if (window.teacherModule?.initOcrUpload) {
            window.teacherModule.initOcrUpload()
          }
        }
        return
      }

      const targetSection = document.getElementById('page-' + targetPage)
      if (targetSection) {
        targetSection.classList.add('active')
      } else {
        window.location.href = targetPage + '.html'
      }
    })
  })
}

/**
 * 初始化教师用户信息
 */
function initTeacherUser() {
  try {
    const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{"name":"海老师","role":"teacher","school":"市第一中学"}')
    const userNameEl = document.getElementById('user-name')
    const userSchoolEl = document.getElementById('user-school')
    const userAvatarEl = document.getElementById('user-avatar')

    if (userNameEl) userNameEl.textContent = user.name || '用户'
    if (userSchoolEl) userSchoolEl.textContent = user.school || ''
    if (userAvatarEl) userAvatarEl.textContent = (user.name || 'U').charAt(0)
  } catch (e) {
    console.error('初始化用户信息失败:', e)
  }
}

/**
 * 学生页初始化
 */
function initStudentPage() {
  console.log('Student page initialized')
}

/**
 * 初始化当前页面
 */
export function initPage(pageName) {
  const initializer = pageInitializers[pageName]
  if (initializer) {
    initializer()
  } else {
    console.warn('Unknown page:', pageName)
  }
}

// 导出给全局使用
if (typeof window !== 'undefined') {
  window.ChemAI = {
    initPage,
    authService,
    Toast,
    teacherModule,
    studentModule,
    studentNotificationsModule,
    teacherNotificationModule,
    reviewCenterModule
  }
}
