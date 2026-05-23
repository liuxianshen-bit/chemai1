/**
 * 家长端模块统一导出
 */

export * from './home.js'
export * from './reports.js'
export * from './notifications.js'
export * from './settings.js'

// 初始化入口
import { parentService, isLoggedIn, getCurrentUser } from '../../services/parent.js'
import { initParentHome } from './home.js'
import { initParentReports } from './reports.js'
import { initParentNotifications } from './notifications.js'
import { initParentSettings } from './settings.js'
import { showBindModal } from './home.js'

export async function initParentModule() {
  // 检查登录状态
  if (!isLoggedIn()) {
    window.location.href = '/login.html'
    return
  }

  // 初始化首页
  await initParentHome()
}

// Tab切换处理
const tabHandlers = {
  home: initParentHome,
  reports: initParentReports,
  notifications: initParentNotifications,
  settings: initParentSettings
}

export function switchTab(tabName) {
  // 更新底部导航状态
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.classList.remove('active')
    if (tab.dataset.tab === tabName) {
      tab.classList.add('active')
    }
  })

  // 切换内容区
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.remove('active')
  })
  const targetContent = document.getElementById(`tab-${tabName}`)
  if (targetContent) {
    targetContent.classList.add('active')
  }

  // 调用对应tab的初始化函数
  const handler = tabHandlers[tabName]
  if (handler) {
    handler()
  }
}

// 导出给window
if (typeof window !== 'undefined') {
  window.parentModule = {
    initParentModule,
    switchTab,
    showBindModal,
    // 从home.js
    initParentHome,
    showChildDetail: () => {},
    // 从reports.js
    initParentReports,
    // 从notifications.js
    initParentNotifications,
    markNotificationRead: () => {},
    loadMoreNotifications: () => {},
    // 从settings.js
    initParentSettings,
    unbindChild: () => {},
    logout: () => {}
  }
}
