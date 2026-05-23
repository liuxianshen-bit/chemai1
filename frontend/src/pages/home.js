/**
 * 首页 - Home Page
 */
import { authService } from '../services/index.js'
import { showLoading, hideLoading } from '../components/index.js'

export function initHome() {
  const user = authService.getCurrentUserFromSession()
  if (!user) {
    window.location.href = '/login.html'
    return
  }

  renderHomePage(user)
}

function renderHomePage(user) {
  const container = document.getElementById('app')
  if (!container) return

  container.innerHTML = `
    <div class="home-page">
      <header class="home-header">
        <h1>欢迎回来，${user.name || user.username}</h1>
        <span class="user-role role-${user.role}">${getRoleName(user.role)}</span>
      </header>

      <div class="home-content">
        <div class="stats-grid" id="stats-grid">
          <!-- 动态加载统计卡片 -->
        </div>

        <div class="quick-actions">
          <h2>快捷操作</h2>
          <div class="action-buttons" id="action-buttons">
            <!-- 根据角色动态生成 -->
          </div>
        </div>
      </div>
    </div>
  `

  loadQuickStats(user)
  renderQuickActions(user)
}

function getRoleName(role) {
  const roleNames = {
    admin: '管理员',
    teacher: '教师',
    student: '学生',
    '学科组长': '学科组长',
    '教务管理员': '教务管理员'
  }
  return roleNames[role] || role
}

async function loadQuickStats(user) {
  const statsGrid = document.getElementById('stats-grid')
  if (!statsGrid) return

  // 根据角色加载不同统计
  const stats = []

  if (user.role === 'student') {
    stats.push(
      { label: '待完成练习', value: '-', icon: '📝' },
      { label: '已完成练习', value: '-', icon: '✅' },
      { label: '错题本', value: '-', icon: '❌' }
    )
  } else if (user.role === 'teacher' || user.role === '学科组长' || user.role === '教务管理员') {
    stats.push(
      { label: '学生总数', value: '-', icon: '👥' },
      { label: '待审核', value: '-', icon: '⏳' },
      { label: '今日任务', value: '-', icon: '📋' }
    )
  } else if (user.role === 'admin') {
    stats.push(
      { label: '教师总数', value: '-', icon: '👨‍🏫' },
      { label: '学生总数', value: '-', icon: '👨‍🎓' },
      { label: '班级总数', value: '-', icon: '🏫' }
    )
  }

  statsGrid.innerHTML = stats.map(stat => `
    <div class="stat-card">
      <span class="stat-icon">${stat.icon}</span>
      <span class="stat-value">${stat.value}</span>
      <span class="stat-label">${stat.label}</span>
    </div>
  `).join('')
}

function renderQuickActions(user) {
  const actionButtons = document.getElementById('action-buttons')
  if (!actionButtons) return

  const actions = []

  if (user.role === 'student') {
    actions.push(
      { text: '开始练习', href: '/practice.html', icon: '▶️' },
      { text: '查看报告', href: '/report.html', icon: '📊' },
      { text: '错题本', href: '/wrong.html', icon: '📒' }
    )
  } else if (user.role === 'teacher' || user.role === '学科组长' || user.role === '教务管理员') {
    actions.push(
      { text: '创建考试', href: '/exam.html?action=create', icon: '📝' },
      { text: '题目管理', href: '/question.html', icon: '📚' },
      { text: '学生管理', href: '/students.html', icon: '👥' },
      { text: '学情报告', href: '/report.html', icon: '📊' }
    )
  } else if (user.role === 'admin') {
    actions.push(
      { text: '教师管理', href: '/teachers.html', icon: '👨‍🏫' },
      { text: '学生管理', href: '/students.html', icon: '👨‍🎓' },
      { text: '班级管理', href: '/classes.html', icon: '🏫' },
      { text: '系统设置', href: '/settings.html', icon: '⚙️' }
    )
  }

  actionButtons.innerHTML = actions.map(action => `
    <a href="${action.href}" class="action-btn">
      <span class="action-icon">${action.icon}</span>
      <span class="action-text">${action.text}</span>
    </a>
  `).join('')
}

export default { initHome }
