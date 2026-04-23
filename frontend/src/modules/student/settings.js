/**
 * 学生端 - 设置模块
 */
import { authService, userService } from '../../services/index.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

// 全局状态
let currentSettings = {
  notifications: {
    push_enabled: true,
    daily_reminder: true,
    reminder_time: '20:00',
    sound_enabled: true
  },
  learning: {
    daily_goal: 10,
    difficulty_preference: 'medium',
    auto_next: true
  }
}

/**
 * 初始化设置模块
 */
export async function initSettingsModule() {
  const container = document.getElementById('settings-container')
  if (!container) return

  await loadSettings()
  bindSettingsEvents()
}

/**
 * 加载设置
 */
export async function loadSettings() {
  try {
    const result = await userService.getUserSettings()

    if (result.success && result.data) {
      currentSettings = { ...currentSettings, ...result.data }
    }

    renderSettings()
  } catch (error) {
    console.error('加载设置失败:', error)
    renderSettings()
  }
}

/**
 * 渲染设置页面
 */
function renderSettings() {
  const container = document.getElementById('settings-container')
  if (!container) return

  container.innerHTML = `
    <div class="settings-page">
      <h2 class="page-title">设置</h2>

      <!-- 通知设置 -->
      <section class="settings-section">
        <h3 class="section-title">通知设置</h3>
        <div class="settings-list">
          <div class="settings-item">
            <div class="settings-info">
              <span class="settings-label">推送通知</span>
              <span class="settings-desc">接收练习提醒和成绩通知</span>
            </div>
            <label class="toggle">
              <input type="checkbox" id="setting-push" ${currentSettings.notifications.push_enabled ? 'checked' : ''}>
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="settings-item">
            <div class="settings-info">
              <span class="settings-label">每日提醒</span>
              <span class="settings-desc">固定时间提醒学习</span>
            </div>
            <label class="toggle">
              <input type="checkbox" id="setting-daily-reminder" ${currentSettings.notifications.daily_reminder ? 'checked' : ''}>
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="settings-item">
            <div class="settings-info">
              <span class="settings-label">提醒时间</span>
            </div>
            <input type="time" id="setting-reminder-time" class="form-input time-input"
              value="${currentSettings.notifications.reminder_time || '20:00'}">
          </div>
          <div class="settings-item">
            <div class="settings-info">
              <span class="settings-label">提示音</span>
            </div>
            <label class="toggle">
              <input type="checkbox" id="setting-sound" ${currentSettings.notifications.sound_enabled ? 'checked' : ''}>
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
      </section>

      <!-- 学习设置 -->
      <section class="settings-section">
        <h3 class="section-title">学习设置</h3>
        <div class="settings-list">
          <div class="settings-item">
            <div class="settings-info">
              <span class="settings-label">每日目标</span>
              <span class="settings-desc">每日完成题目数</span>
            </div>
            <select id="setting-daily-goal" class="form-input select-input">
              <option value="5" ${currentSettings.learning.daily_goal === 5 ? 'selected' : ''}>5题</option>
              <option value="10" ${currentSettings.learning.daily_goal === 10 ? 'selected' : ''}>10题</option>
              <option value="15" ${currentSettings.learning.daily_goal === 15 ? 'selected' : ''}>15题</option>
              <option value="20" ${currentSettings.learning.daily_goal === 20 ? 'selected' : ''}>20题</option>
            </select>
          </div>
          <div class="settings-item">
            <div class="settings-info">
              <span class="settings-label">难度偏好</span>
            </div>
            <select id="setting-difficulty" class="form-input select-input">
              <option value="easy" ${currentSettings.learning.difficulty_preference === 'easy' ? 'selected' : ''}>简单</option>
              <option value="medium" ${currentSettings.learning.difficulty_preference === 'medium' ? 'selected' : ''}>中等</option>
              <option value="hard" ${currentSettings.learning.difficulty_preference === 'hard' ? 'selected' : ''}>困难</option>
            </select>
          </div>
          <div class="settings-item">
            <div class="settings-info">
              <span class="settings-label">自动下一题</span>
              <span class="settings-desc">答题后自动跳转到下一题</span>
            </div>
            <label class="toggle">
              <input type="checkbox" id="setting-auto-next" ${currentSettings.learning.auto_next ? 'checked' : ''}>
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
      </section>

      <!-- 账号设置 -->
      <section class="settings-section">
        <h3 class="section-title">账号设置</h3>
        <div class="settings-list">
          <div class="settings-item clickable" onclick="showChangePassword()">
            <div class="settings-info">
              <span class="settings-label">修改密码</span>
            </div>
            <span class="settings-arrow">›</span>
          </div>
          <div class="settings-item clickable" onclick="logout()">
            <div class="settings-info">
              <span class="settings-label text-error">退出登录</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 关于 -->
      <section class="settings-section">
        <h3 class="section-title">关于</h3>
        <div class="settings-list">
          <div class="settings-item">
            <div class="settings-info">
              <span class="settings-label">版本</span>
            </div>
            <span class="settings-value">v2.0.0</span>
          </div>
          <div class="settings-item clickable" onclick="showPrivacyPolicy()">
            <div class="settings-info">
              <span class="settings-label">隐私政策</span>
            </div>
            <span class="settings-arrow">›</span>
          </div>
          <div class="settings-item clickable" onclick="showTermsOfService()">
            <div class="settings-info">
              <span class="settings-label">服务条款</span>
            </div>
            <span class="settings-arrow">›</span>
          </div>
        </div>
      </section>
    </div>
  `
}

/**
 * 绑定设置事件
 */
function bindSettingsEvents() {
  // 通知设置
  document.addEventListener('change', async (e) => {
    if (e.target.id === 'setting-push') {
      currentSettings.notifications.push_enabled = e.target.checked
      await saveSettings()
    }
    if (e.target.id === 'setting-daily-reminder') {
      currentSettings.notifications.daily_reminder = e.target.checked
      await saveSettings()
    }
    if (e.target.id === 'setting-sound') {
      currentSettings.notifications.sound_enabled = e.target.checked
      await saveSettings()
    }
    if (e.target.id === 'setting-reminder-time') {
      currentSettings.notifications.reminder_time = e.target.value
      await saveSettings()
    }
    if (e.target.id === 'setting-daily-goal') {
      currentSettings.learning.daily_goal = parseInt(e.target.value)
      await saveSettings()
    }
    if (e.target.id === 'setting-difficulty') {
      currentSettings.learning.difficulty_preference = e.target.value
      await saveSettings()
    }
    if (e.target.id === 'setting-auto-next') {
      currentSettings.learning.auto_next = e.target.checked
      await saveSettings()
    }
  })
}

/**
 * 保存设置
 */
export async function saveSettings() {
  try {
    const result = await userService.updateUserSettings(currentSettings)

    if (result.success) {
      // 不需要Toast，避免频繁打扰
    }
  } catch (error) {
    console.error('保存设置失败:', error)
  }
}

/**
 * 显示修改密码弹窗
 */
export function showChangePassword() {
  const modal = document.getElementById('change-password-modal')
  if (!modal) return

  modal.style.display = 'flex'
}

/**
 * 修改密码
 */
export async function changePassword(oldPassword, newPassword) {
  showLoading()

  try {
    const result = await userService.changePassword(oldPassword, newPassword)

    if (result.success) {
      Toast.success('密码修改成功')
      closeChangePasswordModal()
    } else {
      Toast.error(result.message || '修改失败')
    }
  } catch (error) {
    Toast.error('修改失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 关闭修改密码弹窗
 */
export function closeChangePasswordModal() {
  const modal = document.getElementById('change-password-modal')
  if (modal) modal.style.display = 'none'
}

/**
 * 退出登录
 */
export async function logout() {
  if (!confirm('确定要退出登录吗？')) return

  try {
    await authService.logout()
    window.location.href = '/login.html'
  } catch (error) {
    Toast.error('退出失败')
  }
}

/**
 * 显示隐私政策
 */
export function showPrivacyPolicy() {
  Toast.info('隐私政策功能开发中')
}

/**
 * 显示服务条款
 */
export function showTermsOfService() {
  Toast.info('服务条款功能开发中')
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.showChangePassword = showChangePassword
  window.changePassword = changePassword
  window.closeChangePasswordModal = closeChangePasswordModal
  window.logout = logout
  window.showPrivacyPolicy = showPrivacyPolicy
  window.showTermsOfService = showTermsOfService
}
