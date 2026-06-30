/**
 * 家长端 - 设置模块
 * 绑定管理、通知偏好、账号设置
 */

import { parentService, logout } from '../../services/parent.js'

let currentChildren = []

export async function initParentSettings() {
  const container = document.getElementById('settings-content')
  if (!container) return

  container.innerHTML = '<div class="loading-state"><p>加载中...</p></div>'

  try {
    const result = await parentService.getChildren()
    currentChildren = result.children || []

    renderSettings(container)
  } catch (error) {
    console.error('加载设置失败:', error)
    container.innerHTML = '<div class="empty-state"><p>加载失败</p></div>'
  }
}

function renderSettings(container) {
  const user = parentService.getCurrentUser()

  container.innerHTML = `
    <div class="settings-section">
      <h3 class="section-title">账号信息</h3>
      <div class="panel">
        <div class="settings-item">
          <div class="settings-item-info">
            <div class="avatar-large">${user?.name?.charAt(0) || '家'}</div>
            <div>
              <div class="settings-item-title">${user?.name || '家长'}</div>
              <div class="settings-item-desc">家长账号</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <h3 class="section-title">已绑定子女</h3>
      <div class="panel">
        ${currentChildren.length > 0 ? currentChildren.map(child => `
          <div class="settings-item">
            <div class="settings-item-info">
              <div class="avatar-small">${child.student_name.charAt(0)}</div>
              <div>
                <div class="settings-item-title">${child.student_name}</div>
                <div class="settings-item-desc">${child.relation} · ${child.grade} ${child.class_name}</div>
              </div>
            </div>
            <button class="btn-text danger" onclick="parentModule.unbindChild('${child.binding_id}')">解除绑定</button>
          </div>
        `).join('') : `
          <div class="settings-item">
            <div class="text-muted">暂无绑定子女</div>
          </div>
        `}
        <div class="settings-item">
          <button class="btn-secondary" style="width: 100%;" onclick="parentModule.showBindModal()">
            <svg viewBox="0 0 24 24" stroke-width="2" width="16" height="16"><path d="M12 5v14M5 12h14"/></svg>
            绑定新子女
          </button>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <h3 class="section-title">通知设置</h3>
      <div class="panel">
        <div class="settings-item toggle-item">
          <div class="settings-item-info">
            <div class="settings-item-title">接收周报</div>
            <div class="settings-item-desc">每周五接收子女学习周报</div>
          </div>
          <label class="toggle">
            <input type="checkbox" checked>
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="settings-item toggle-item">
          <div class="settings-item-info">
            <div class="settings-item-title">成绩预警</div>
            <div class="settings-item-desc">子女成绩下滑时接收通知</div>
          </div>
          <label class="toggle">
            <input type="checkbox" checked>
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="settings-item toggle-item">
          <div class="settings-item-info">
            <div class="settings-item-title">学习提醒</div>
            <div class="settings-item-desc">子女连续未登录时接收通知</div>
          </div>
          <label class="toggle">
            <input type="checkbox" checked>
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <h3 class="section-title">帮助与反馈</h3>
      <div class="panel">
        <div class="settings-item">
          <div class="settings-item-title">常见问题</div>
          <svg viewBox="0 0 24 24" stroke-width="2" width="16" height="16"><path d="M9 18l6-6-6-6"/></svg>
        </div>
        <div class="settings-item">
          <div class="settings-item-title">联系客服</div>
          <svg viewBox="0 0 24 24" stroke-width="2" width="16" height="16"><path d="M9 18l6-6-6-6"/></svg>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <button class="btn-logout" onclick="parentModule.logout()">
        <svg viewBox="0 0 24 24" stroke-width="2" width="20" height="20"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>
        退出登录
      </button>
    </div>

    <div class="version-info">
      <p>智辅化学 家长端 v1.1</p>
    </div>
  `
}

export async function unbindChild(bindingId) {
  if (!confirm('确定要解除绑定吗？')) return

  try {
    const result = await parentService.unbindStudent(bindingId)
    if (result.success) {
      // 重新加载设置页面
      await initParentSettings()
    } else {
      alert(result.message || '解除绑定失败')
    }
  } catch (error) {
    console.error('解除绑定失败:', error)
    alert('解除绑定失败，请重试')
  }
}

export function handleLogout() {
  logout()
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.parentModule = window.parentModule || {}
  window.parentModule.initParentSettings = initParentSettings
  window.parentModule.unbindChild = unbindChild
  window.parentModule.logout = handleLogout
}
