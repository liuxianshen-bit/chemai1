/**
 * Agent 模块 — SSE 连接 + 事件分发 + 消息管理
 */
import { api } from '../../services/api.js'
import { authService } from '../../services/auth.js'

let conversationHistory = []
let currentPersona = 'teacher'

export function initAgentPage() {
  const user = authService.getCurrentUserFromSession()
  currentPersona = user?.role === 'student' ? 'tutor' : 'teacher'
  setupEventListeners()
}

function setupEventListeners() {
  const sendBtn = document.getElementById('agent-send')
  const input = document.getElementById('agent-input')
  if (sendBtn) sendBtn.addEventListener('click', sendMessage)
  if (input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
    })
  }
  // SuggestionChips
  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.dataset.prompt
      if (prompt) sendMessage(prompt)
    })
  })
}

async function sendMessage(text) {
  const input = document.getElementById('agent-input')
  const msg = text || input?.value?.trim()
  if (!msg) return
  if (input) { input.value = ''; input.style.height = 'auto' }

  addMessageBubble('user', msg)
  conversationHistory.push({ role: 'user', content: msg })

  const bubble = addMessageBubble('assistant', '')
  const statusBar = document.getElementById('agent-status')
  showStatus(statusBar, 'thinking', '')

  try {
    const resp = await fetch('/api/agent/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        persona: currentPersona,
        message: msg,
        provider: 'deepseek',
        history: conversationHistory.slice(0, -1),
      }),
    })

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let toolCard = null
    let replyText = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          if (event.type === 'done') break

          switch (event.type) {
            case 'phase':
              showStatus(statusBar, event.phase, event.phase === 'executing' ? statusBar?.dataset?.tool : '')
              break
            case 'text':
              replyText += event.content
              bubble.textContent = replyText
              bubble.scrollIntoView({ block: 'end', behavior: 'smooth' })
              break
            case 'tool_call':
              toolCard = showToolCard(event.name, 'running')
              statusBar.dataset.tool = event.name
              break
            case 'tool_result':
              if (toolCard) updateToolCard(toolCard, event)
              showStatus(statusBar, 'reply', '')
              break
            case 'tool_error':
              if (toolCard) updateToolCard(toolCard, { name: event.name, success: false, result: { error: event.error } })
              break
          }
        } catch (e) { /* skip malformed events */ }
      }
    }

    if (replyText) conversationHistory.push({ role: 'assistant', content: replyText })
    if (statusBar) statusBar.style.display = 'none'
  } catch (err) {
    bubble.textContent = '抱歉，请求失败: ' + err.message
    bubble.className = 'agent-msg assistant error'
    if (statusBar) statusBar.style.display = 'none'
  }
}

function addMessageBubble(role, text) {
  const container = document.getElementById('agent-messages')
  if (!container) return { textContent: '' }
  const el = document.createElement('div')
  el.className = `agent-msg ${role}`
  el.textContent = text
  container.appendChild(el)
  el.scrollIntoView({ block: 'end', behavior: 'smooth' })
  return el
}

function showToolCard(name, status) {
  const container = document.getElementById('agent-messages')
  if (!container) return null
  const card = document.createElement('div')
  card.className = 'tool-card'
  card.innerHTML = `<div class="tool-card-header">
    <span class="tool-icon">🔧</span>
    <span class="tool-name">${name}</span>
    <span class="tool-status ${status}">${status === 'running' ? '执行中...' : '完成'}</span>
  </div><div class="tool-card-body" style="display:none"></div>`
  container.appendChild(card)
  return card
}

function updateToolCard(card, event) {
  const statusEl = card.querySelector('.tool-status')
  const bodyEl = card.querySelector('.tool-card-body')
  statusEl.className = `tool-status ${event.success ? 'success' : 'error'}`
  statusEl.textContent = event.success ? '✅' : '❌'
  bodyEl.style.display = 'block'
  bodyEl.textContent = JSON.stringify(event.result, null, 2)
  card.addEventListener('click', () => {
    bodyEl.style.display = bodyEl.style.display === 'none' ? 'block' : 'none'
  })
}

function showStatus(bar, phase, tool) {
  if (!bar) return
  const labels = { thinking: '思考中...', executing: `执行: ${tool}`, reply: '回复中...' }
  bar.style.display = 'flex'
  bar.querySelector('.status-text').textContent = labels[phase] || phase
}

window.sendAgentMessage = sendMessage
