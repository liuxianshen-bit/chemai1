/**
 * ChemAI Agent Chat — SSE 流式对话
 */
(function () {
  'use strict'
  var history = []

  // ─── 事件绑定 ───
  document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('chat-input')
    if (input) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
        autoResize(input)
      })
      input.addEventListener('input', function () { autoResize(input) })
    }

    // Suggestion chips
    document.querySelectorAll('.chip[data-prompt]').forEach(function (c) {
      c.addEventListener('click', function () { sendMessage(c.dataset.prompt) })
    })
  })

  function autoResize(el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  // ─── 全局发送入口 ───
  window.sendMessage = function (text) {
    var input = document.getElementById('chat-input')
    var msg = text || input.value.trim()
    if (!msg) return
    if (!text) { input.value = ''; input.style.height = 'auto' }

    addMsg('user', msg)
    history.push({ role: 'user', content: msg })

    var bubble = addMsg('ai', '')
    showStatus(true, '思考中...', '')

    fetch('/api/agent/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona: 'teacher', message: msg, provider: 'deepseek', history: history.slice(0, -1) })
    }).then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status)
      return streamResponse(resp, bubble)
    }).catch(function (e) {
      bubble.innerHTML = '<span style="color:#C53030">抱歉，请求失败: ' + e.message + '</span>'
      showStatus(false)
    })
  }

  // ─── SSE 流式读取 ───
  async function streamResponse(resp, bubble) {
    var reader = resp.body.getReader()
    var decoder = new TextDecoder()
    var buffer = '', reply = '', toolCard = null

    while (true) {
      var r = await reader.read()
      if (r.done) break
      buffer += decoder.decode(r.value, { stream: true })
      var lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (var i = 0; i < lines.length; i++) {
        var line = lines[i]
        if (!line.startsWith('data: ')) continue
        try {
          var evt = JSON.parse(line.slice(6))
          if (evt.type === 'done') break
          switch (evt.type) {
            case 'phase':
              showStatus(true, evt.phase === 'thinking' ? '思考中...' : evt.phase === 'executing' ? '执行中...' : '回复中...', '')
              break
            case 'text':
              reply += evt.content
              bubble.innerHTML = renderMarkdown(reply)
              scrollBottom()
              break
            case 'tool_call':
              bubble.innerHTML = ''
              toolCard = addToolCard(evt.name, 'running')
              showStatus(true, '执行: ' + evt.name, '')
              break
            case 'tool_result':
              if (toolCard) updateToolCard(toolCard, evt)
              showStatus(true, '回复中...', '')
              break
            case 'tool_error':
              if (toolCard) updateToolCard(toolCard, { success: false, result: { error: evt.error }, name: evt.name })
              break
          }
        } catch (e) {}
      }
    }

    if (reply) {
      bubble.innerHTML = renderMarkdown(reply)
      history.push({ role: 'assistant', content: reply })
    }
    showStatus(false)
  }

  // ─── UI Helpers ───
  function addMsg(role, text) {
    var container = document.getElementById('chat-messages')
    var el = document.createElement('div')
    el.className = role === 'user' ? 'msg-user' : 'msg-ai'
    if (role === 'ai') {
      el.innerHTML = '<div class="ai-avatar"><span class="material-symbols-outlined text-[16px]">psychology</span> AI 教研助手</div>' + text
    } else {
      el.textContent = text
    }
    container.appendChild(el)
    scrollBottom()
    return el
  }

  function addToolCard(name, status) {
    var container = document.getElementById('chat-messages')
    var card = document.createElement('div')
    card.className = 'tool-card'
    card.innerHTML = '<div class="tool-card-header">' +
      '<span class="material-symbols-outlined text-[16px]" style="color:#455f88">build</span>' +
      '<span style="font-weight:600;color:#002045">' + name + '</span>' +
      '<span style="color:#13696a;font-size:11px">执行中...</span>' +
      '</div><div class="tool-card-body"></div>'
    container.appendChild(card)
    scrollBottom()
    return card
  }

  function updateToolCard(card, evt) {
    var status = card.querySelector('.tool-card-header span:last-child')
    status.textContent = evt.success !== false ? '✅ 完成' : '❌ 失败'
    status.style.color = evt.success !== false ? '#2F855A' : '#C53030'
    var body = card.querySelector('.tool-card-body')
    body.style.display = 'block'
    body.textContent = JSON.stringify(evt.result, null, 2)
    card.onclick = function () { body.style.display = body.style.display === 'none' ? 'block' : 'none' }
  }

  function showStatus(show, text, tool) {
    var bar = document.getElementById('agent-status')
    var txt = document.getElementById('status-text')
    if (!bar || !txt) return
    bar.style.display = show ? 'flex' : 'none'
    txt.textContent = text || ''
  }

  function scrollBottom() {
    var el = document.getElementById('chat-messages')
    if (el) { el.scrollTop = el.scrollHeight }
  }

  function renderMarkdown(text) {
    return text
      .replace(/### (.+)/g, '<h3 style="font-family:Manrope;font-size:16px;font-weight:600;margin:8px 0 4px;color:#002045">$1</h3>')
      .replace(/## (.+)/g, '<h2 style="font-family:Manrope;font-size:18px;font-weight:700;margin:12px 0 6px;color:#002045">$1</h2>')
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      .replace(/\*(.+?)\*/g, '<i>$1</i>')
      .replace(/`([^`]+)`/g, '<code style="font-family:JetBrains Mono;background:rgba(0,0,0,.05);padding:1px 4px;border-radius:3px">$1</code>')
      .replace(/\n/g, '<br>')
      .replace(/- (.+)/g, '· $1')
  }
})()
