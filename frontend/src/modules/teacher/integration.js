/**
 * 教师端 - LMS集成模块
 */

import { integrationService } from '../../services/integration.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

let currentTab = 'dingtalk'
let webhookList = []
let apiKeys = []
let sftpConfig = null

/**
 * 初始化集成模块
 */
export async function initIntegrationModule() {
  const container = document.getElementById('integration-container')
  if (!container) return

  showLoading('加载集成配置...')

  try {
    await Promise.all([
      loadLmsConfig(),
      loadWebhooks(),
      loadApiKeys(),
      loadSftpConfig()
    ])
    renderIntegration(container)
  } catch (e) {
    console.error('初始化集成模块失败', e)
    Toast.error('加载失败')
  } finally {
    hideLoading()
  }
}

/**
 * 加载LMS配置
 */
async function loadLmsConfig() {
  const result = await integrationService.getLmsConfig()
  if (result.success) {
    window._lmsConfig = result.platforms || {}
  }
}

/**
 * 加载Webhooks
 */
async function loadWebhooks() {
  const result = await integrationService.getWebhooks()
  if (result.success) {
    webhookList = result.webhooks || []
    window._availableEvents = result.available_events || []
  }
}

/**
 * 加载API密钥
 */
async function loadApiKeys() {
  const result = await integrationService.getApiKeys()
  if (result.success) {
    apiKeys = result.keys || []
  }
}

/**
 * 加载SFTP配置
 */
async function loadSftpConfig() {
  const result = await integrationService.getSftpConfig()
  if (result.success) {
    sftpConfig = result
  }
}

/**
 * 渲染集成页面
 */
function renderIntegration(container) {
  container.innerHTML = `
    <div class="integration-tabs" style="display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap;">
      <button class="integration-tab ${currentTab === 'dingtalk' ? 'active' : ''}"
              onclick="integrationModule.switchTab('dingtalk')"
              style="padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem;
                     ${currentTab === 'dingtalk' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
        钉钉
      </button>
      <button class="integration-tab ${currentTab === 'wecom' ? 'active' : ''}"
              onclick="integrationModule.switchTab('wecom')"
              style="padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem;
                     ${currentTab === 'wecom' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
        企业微信
      </button>
      <button class="integration-tab ${currentTab === 'webhook' ? 'active' : ''}"
              onclick="integrationModule.switchTab('webhook')"
              style="padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem;
                     ${currentTab === 'webhook' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
        Webhook
      </button>
      <button class="integration-tab ${currentTab === 'lti' ? 'active' : ''}"
              onclick="integrationModule.switchTab('lti')"
              style="padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem;
                     ${currentTab === 'lti' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
        LTI 1.3
      </button>
      <button class="integration-tab ${currentTab === 'apikey' ? 'active' : ''}"
              onclick="integrationModule.switchTab('apikey')"
              style="padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem;
                     ${currentTab === 'apikey' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
        API密钥
      </button>
      <button class="integration-tab ${currentTab === 'sftp' ? 'active' : ''}"
              onclick="integrationModule.switchTab('sftp')"
              style="padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem;
                     ${currentTab === 'sftp' ? 'background: var(--accent); color: white;' : 'background: var(--bg-tertiary); color: var(--text-secondary);'}">
        SFTP
      </button>
    </div>

    <div id="integration-content">
      ${renderCurrentTab()}
    </div>
  `
}

/**
 * 渲染当前Tab内容
 */
function renderCurrentTab() {
  switch (currentTab) {
    case 'dingtalk':
      return renderDingtalkConfig()
    case 'wecom':
      return renderWecomConfig()
    case 'webhook':
      return renderWebhookConfig()
    case 'lti':
      return renderLtiConfig()
    case 'apikey':
      return renderApiKeyConfig()
    case 'sftp':
      return renderSftpConfig()
    default:
      return ''
  }
}

/**
 * 钉钉配置
 */
function renderDingtalkConfig() {
  const config = window._lmsConfig?.dingtalk || { enabled: false, connected: false }
  return `
    <div class="panel">
      <div class="panel-header">
        <h3 class="panel-title">钉钉配置</h3>
        <label style="display: flex; align-items: center; gap: 8px; font-size: 0.875rem;">
          <input type="checkbox" id="dingtalk-enabled" ${config.enabled ? 'checked' : ''}
                  onchange="integrationModule.togglePlatform('dingtalk', this.checked)">
          启用钉钉集成
        </label>
      </div>
      <div class="panel-body">
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">AppKey</label>
          <input type="text" id="dingtalk-appkey" placeholder="请输入AppKey"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">AppSecret</label>
          <input type="password" id="dingtalk-appsecret" placeholder="请输入AppSecret"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">AgentID</label>
          <input type="text" id="dingtalk-agentid" placeholder="请输入AgentID"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div style="display: flex; gap: 12px;">
          <button class="btn-primary" onclick="integrationModule.saveDingtalk()">保存配置</button>
          <button class="btn-secondary" onclick="integrationModule.testDingtalk()">测试连接</button>
        </div>
      </div>
    </div>
  `
}

/**
 * 企业微信配置
 */
function renderWecomConfig() {
  const config = window._lmsConfig?.wecom || { enabled: false, connected: false }
  return `
    <div class="panel">
      <div class="panel-header">
        <h3 class="panel-title">企业微信配置</h3>
        <label style="display: flex; align-items: center; gap: 8px; font-size: 0.875rem;">
          <input type="checkbox" id="wecom-enabled" ${config.enabled ? 'checked' : ''}
                  onchange="integrationModule.togglePlatform('wecom', this.checked)">
          启用企业微信集成
        </label>
      </div>
      <div class="panel-body">
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">CorpID</label>
          <input type="text" id="wecom-corpid" placeholder="请输入CorpID"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">CorpSecret</label>
          <input type="password" id="wecom-corpsecret" placeholder="请输入CorpSecret"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">AgentID</label>
          <input type="text" id="wecom-agentid" placeholder="请输入AgentID"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div style="display: flex; gap: 12px;">
          <button class="btn-primary" onclick="integrationModule.saveWecom()">保存配置</button>
          <button class="btn-secondary" onclick="integrationModule.testWecom()">测试连接</button>
        </div>
      </div>
    </div>
  `
}

/**
 * Webhook配置
 */
function renderWebhookConfig() {
  const eventTypes = window._availableEvents || ['exam.created', 'warning.triggered', 'report.generated']
  return `
    <div class="panel">
      <div class="panel-header">
        <h3 class="panel-title">Webhook配置</h3>
      </div>
      <div class="panel-body">
        <div id="webhook-list" style="margin-bottom: 20px;">
          ${webhookList.length === 0 ? `
            <div class="empty-state" style="padding: 24px;">
              <p style="color: var(--text-muted);">暂无注册的Webhook</p>
            </div>
          ` : webhookList.map(wh => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 8px;">
              <div>
                <span style="font-weight: 600; color: var(--text-primary);">${wh.event_type}</span>
                <span style="margin-left: 12px; font-size: 0.75rem; color: var(--text-muted);">${wh.url}</span>
              </div>
              <div style="display: flex; gap: 8px;">
                <button class="btn-secondary btn-sm" onclick="integrationModule.testWebhook('${wh.event_type}', '${wh.url}')">测试</button>
                <button class="btn-secondary btn-sm" onclick="integrationModule.deleteWebhook('${wh.event_type}')" style="color: var(--error);">删除</button>
              </div>
            </div>
          `).join('')}
        </div>

        <div style="border-top: 1px solid var(--border); padding-top: 20px;">
          <h4 style="font-size: 0.875rem; margin-bottom: 12px;">注册新Webhook</h4>
          <div class="form-group" style="margin-bottom: 12px;">
            <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">事件类型</label>
            <select id="webhook-event-type" style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
              ${eventTypes.map(e => `<option value="${e}">${e}</option>`).join('')}
            </select>
          </div>
          <div class="form-group" style="margin-bottom: 12px;">
            <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">Webhook URL</label>
            <input type="text" id="webhook-url" placeholder="https://your-server.com/webhook"
                   style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
          </div>
          <div class="form-group" style="margin-bottom: 12px;">
            <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">密钥（可选）</label>
            <input type="password" id="webhook-secret" placeholder="用于签名验证"
                   style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
          </div>
          <button class="btn-primary" onclick="integrationModule.addWebhook()">添加Webhook</button>
        </div>
      </div>
    </div>
  `
}

/**
 * LTI 1.3配置
 */
function renderLtiConfig() {
  return `
    <div class="panel">
      <div class="panel-header">
        <h3 class="panel-title">LTI 1.3 Provider配置</h3>
      </div>
      <div class="panel-body">
        <div style="padding: 24px; text-align: center; color: var(--text-muted);">
          <p style="margin-bottom: 16px;">LTI 1.3功能开发中</p>
          <p style="font-size: 0.75rem;">即将支持Canvas、Blackboard、Moodle等主流LMS平台</p>
        </div>
        <div style="border-top: 1px solid var(--border); padding-top: 20px;">
          <h4 style="font-size: 0.875rem; margin-bottom: 12px;">LTI深度链接</h4>
          <div class="form-group" style="margin-bottom: 12px;">
            <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">Platform Issuer</label>
            <input type="text" id="lti-issuer" placeholder="https://canvas.instructure.com"
                   style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
          </div>
          <div class="form-group" style="margin-bottom: 12px;">
            <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">Deployment ID</label>
            <input type="text" id="lti-deployment" placeholder="1"
                   style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
          </div>
          <button class="btn-primary" disabled style="opacity: 0.6;">获取深度链接（开发中）</button>
        </div>
      </div>
    </div>
  `
}

/**
 * API密钥配置
 */
function renderApiKeyConfig() {
  return `
    <div class="panel">
      <div class="panel-header">
        <h3 class="panel-title">API密钥管理</h3>
        <button class="btn-primary btn-sm" onclick="integrationModule.showCreateApiKey()">创建密钥</button>
      </div>
      <div class="panel-body">
        <div id="api-key-list">
          ${apiKeys.length === 0 ? `
            <div class="empty-state" style="padding: 24px;">
              <p style="color: var(--text-muted);">暂无API密钥</p>
            </div>
          ` : apiKeys.map(key => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 8px;">
              <div>
                <span style="font-weight: 600; color: var(--text-primary);">${key.name}</span>
                <span style="margin-left: 12px; font-size: 0.75rem; color: var(--text-muted);">${key.api_key}</span>
              </div>
              <button class="btn-secondary btn-sm" onclick="integrationModule.deleteApiKey('${key.api_key}')" style="color: var(--error);">删除</button>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `
}

/**
 * SFTP配置
 */
function renderSftpConfig() {
  const config = sftpConfig || { enabled: false }
  return `
    <div class="panel">
      <div class="panel-header">
        <h3 class="panel-title">SFTP配置</h3>
        <label style="display: flex; align-items: center; gap: 8px; font-size: 0.875rem;">
          <input type="checkbox" id="sftp-enabled" ${config.enabled ? 'checked' : ''}
                  onchange="integrationModule.toggleSftp(this.checked)">
          启用SFTP
        </label>
      </div>
      <div class="panel-body">
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">主机地址</label>
          <input type="text" id="sftp-host" placeholder="sftp.example.com"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">端口</label>
          <input type="number" id="sftp-port" value="22"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">用户名</label>
          <input type="text" id="sftp-username" placeholder="username"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">密码</label>
          <input type="password" id="sftp-password" placeholder="password"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">上传路径</label>
          <input type="text" id="sftp-upload-path" placeholder="/upload"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label style="display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">下载路径</label>
          <input type="text" id="sftp-download-path" placeholder="/download"
                 style="width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.875rem;">
        </div>
        <div style="display: flex; gap: 12px;">
          <button class="btn-primary" onclick="integrationModule.saveSftp()">保存配置</button>
          <button class="btn-secondary" onclick="integrationModule.testSftp()">测试连接</button>
        </div>
      </div>
    </div>
  `
}

/**
 * 切换Tab
 */
export function switchTab(tab) {
  currentTab = tab
  const container = document.getElementById('integration-container')
  if (container) {
    const content = document.getElementById('integration-content')
    if (content) {
      content.innerHTML = renderCurrentTab()
    }
    // 更新tab样式
    document.querySelectorAll('.integration-tab').forEach(btn => {
      btn.classList.remove('active')
      if (btn.textContent.includes(tab === 'dingtalk' ? '钉钉' : tab === 'wecom' ? '企业微信' : tab === 'webhook' ? 'Webhook' : tab === 'lti' ? 'LTI' : tab === 'apikey' ? 'API' : 'SFTP')) {
        btn.classList.add('active')
      }
    })
  }
}

/**
 * 切换平台启用状态
 */
export async function togglePlatform(platform, enabled) {
  // 保存配置
  await savePlatformConfig(platform, { enabled })
}

/**
 * 保存钉钉配置
 */
export async function saveDingtalk() {
  const enabled = document.getElementById('dingtalk-enabled')?.checked || false
  const config = {
    platform: 'dingtalk',
    enabled,
    app_key: document.getElementById('dingtalk-appkey')?.value,
    app_secret: document.getElementById('dingtalk-appsecret')?.value,
    agent_id: document.getElementById('dingtalk-agentid')?.value
  }

  const result = await integrationService.saveLmsConfig(config)
  if (result.success) {
    Toast.success('钉钉配置已保存')
  } else {
    Toast.error('保存失败')
  }
}

/**
 * 测试钉钉连接
 */
export async function testDingtalk() {
  const config = {
    app_key: document.getElementById('dingtalk-appkey')?.value,
    app_secret: document.getElementById('dingtalk-appsecret')?.value,
    agent_id: document.getElementById('dingtalk-agentid')?.value
  }

  showLoading('测试连接中...')
  try {
    const result = await integrationService.testLmsConnection('dingtalk', config)
    if (result.success) {
      Toast.success('连接成功')
    } else {
      Toast.error('连接失败：' + (result.message || '未知错误'))
    }
  } catch (e) {
    Toast.error('连接失败：' + e.message)
  } finally {
    hideLoading()
  }
}

/**
 * 保存企业微信配置
 */
export async function saveWecom() {
  const enabled = document.getElementById('wecom-enabled')?.checked || false
  const config = {
    platform: 'wecom',
    enabled,
    corp_id: document.getElementById('wecom-corpid')?.value,
    corp_secret: document.getElementById('wecom-corpsecret')?.value,
    agent_id: document.getElementById('wecom-agentid')?.value
  }

  const result = await integrationService.saveLmsConfig(config)
  if (result.success) {
    Toast.success('企业微信配置已保存')
  } else {
    Toast.error('保存失败')
  }
}

/**
 * 测试企业微信连接
 */
export async function testWecom() {
  const config = {
    corp_id: document.getElementById('wecom-corpid')?.value,
    corp_secret: document.getElementById('wecom-corpsecret')?.value,
    agent_id: document.getElementById('wecom-agentid')?.value
  }

  showLoading('测试连接中...')
  try {
    const result = await integrationService.testLmsConnection('wecom', config)
    if (result.success) {
      Toast.success('连接成功')
    } else {
      Toast.error('连接失败：' + (result.message || '未知错误'))
    }
  } catch (e) {
    Toast.error('连接失败：' + e.message)
  } finally {
    hideLoading()
  }
}

/**
 * 添加Webhook
 */
export async function addWebhook() {
  const eventType = document.getElementById('webhook-event-type')?.value
  const url = document.getElementById('webhook-url')?.value
  const secret = document.getElementById('webhook-secret')?.value

  if (!url) {
    Toast.error('请输入Webhook URL')
    return
  }

  const result = await integrationService.registerWebhook(eventType, url, secret)
  if (result.success) {
    Toast.success('Webhook已添加')
    await loadWebhooks()
    const container = document.getElementById('integration-container')
    if (container) renderIntegration(container)
  } else {
    Toast.error('添加失败')
  }
}

/**
 * 测试Webhook
 */
export async function testWebhook(eventType, url) {
  showLoading('发送测试事件...')
  try {
    const result = await integrationService.testWebhook(eventType, url)
    if (result.success) {
      Toast.success('测试事件已发送')
    } else {
      Toast.error('发送失败')
    }
  } catch (e) {
    Toast.error('发送失败：' + e.message)
  } finally {
    hideLoading()
  }
}

/**
 * 删除Webhook
 */
export async function deleteWebhook(eventType) {
  if (!confirm('确定要删除此Webhook吗？')) return

  const result = await integrationService.unregisterWebhook(eventType)
  if (result.success) {
    Toast.success('Webhook已删除')
    await loadWebhooks()
    const container = document.getElementById('integration-container')
    if (container) renderIntegration(container)
  } else {
    Toast.error('删除失败')
  }
}

/**
 * 显示创建API密钥弹窗
 */
export function showCreateApiKey() {
  const name = prompt('请输入密钥名称：')
  if (!name) return

  const permissions = prompt('请输入权限（逗号分隔，如：exam:read,warning:write）：', 'exam:read,warning:write')
  if (!permissions) return

  createApiKey(name, permissions.split(',').map(p => p.trim()))
}

/**
 * 创建API密钥
 */
export async function createApiKey(name, permissions) {
  const result = await integrationService.createApiKey(name, permissions)
  if (result.success) {
    Toast.success('API密钥已创建，请妥善保存')
    // 显示密钥（只在创建时显示一次）
    alert(`API Key: ${result.api_key}\nAPI Secret: ${result.api_secret}\n\n请妥善保存，密钥不会再显示！`)
    await loadApiKeys()
    const container = document.getElementById('integration-container')
    if (container) renderIntegration(container)
  } else {
    Toast.error('创建失败')
  }
}

/**
 * 删除API密钥
 */
export async function deleteApiKey(keyId) {
  if (!confirm('确定要删除此API密钥吗？')) return

  const result = await integrationService.deleteApiKey(keyId)
  if (result.success) {
    Toast.success('密钥已删除')
    await loadApiKeys()
    const container = document.getElementById('integration-container')
    if (container) renderIntegration(container)
  } else {
    Toast.error('删除失败')
  }
}

/**
 * 切换SFTP启用状态
 */
export async function toggleSftp(enabled) {
  await saveSftpConfig({ enabled })
}

/**
 * 保存SFTP配置
 */
export async function saveSftp() {
  const config = {
    enabled: document.getElementById('sftp-enabled')?.checked || false,
    host: document.getElementById('sftp-host')?.value,
    port: parseInt(document.getElementById('sftp-port')?.value || '22'),
    username: document.getElementById('sftp-username')?.value,
    password: document.getElementById('sftp-password')?.value,
    upload_path: document.getElementById('sftp-upload-path')?.value,
    download_path: document.getElementById('sftp-download-path')?.value
  }

  const result = await integrationService.saveSftpConfig(config)
  if (result.success) {
    Toast.success('SFTP配置已保存')
  } else {
    Toast.error('保存失败')
  }
}

/**
 * 测试SFTP连接
 */
export async function testSftp() {
  const config = {
    host: document.getElementById('sftp-host')?.value,
    port: parseInt(document.getElementById('sftp-port')?.value || '22'),
    username: document.getElementById('sftp-username')?.value,
    password: document.getElementById('sftp-password')?.value
  }

  showLoading('测试连接中...')
  try {
    const result = await integrationService.testSftpConnection(config)
    if (result.success) {
      Toast.success('连接成功')
    } else {
      Toast.error('连接失败：' + (result.message || '未知错误'))
    }
  } catch (e) {
    Toast.error('连接失败：' + e.message)
  } finally {
    hideLoading()
  }
}

/**
 * 保存平台配置（通用）
 */
async function savePlatformConfig(platform, config) {
  const result = await integrationService.saveLmsConfig({ platform, ...config })
  if (result.success) {
    Toast.success('配置已保存')
  } else {
    Toast.error('保存失败')
  }
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.integrationModule = {
    init: initIntegrationModule,
    switchTab,
    saveDingtalk,
    testDingtalk,
    saveWecom,
    testWecom,
    addWebhook,
    testWebhook,
    deleteWebhook,
    showCreateApiKey,
    createApiKey,
    deleteApiKey,
    toggleSftp,
    saveSftp,
    testSftp,
    togglePlatform
  }
}

export default {
  init: initIntegrationModule,
  switchTab
}
