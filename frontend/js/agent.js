/**
 * ChemAI Agent Chat — SSE 流式对话
 */
(function () {
  'use strict'
  var history = []
  var isSending = false
  var currentConvId = null
  var agentContext = { class_id: '', class_name: '', exam_id: '', exam_name: '', student_id: '', student_name: '' }

  // ─── 历史对话管理 ───
  function getConversations() {
    try { return JSON.parse(localStorage.getItem('chemai_convs') || '[]') } catch(e) { return [] }
  }
  function saveConversations(convs) { localStorage.setItem('chemai_convs', JSON.stringify(convs)) }
  function newConvId() { return 'c' + Date.now() }

  function renderHistory() {
    var el = document.getElementById('hd-list')
    if (!el) return
    var convs = getConversations()
    convs.sort(function(a,b){return b.updated - a.updated})
    el.innerHTML = convs.length ? convs.map(function(c){
      var cls = c.id === currentConvId ? 'history-item active' : 'history-item'
      return '<div class="'+cls+'" onclick="loadConversation(\''+c.id+'\')">' +
        '<span class="title">' + escHtml(c.title || '新对话') + '</span>' +
        '<button class="del" onclick="event.stopPropagation();deleteConversation(\''+c.id+'\')">&times;</button></div>'
    }).join('') : '<div style="font-size:12px;color:#999;padding:16px 8px;text-align:center">暂无历史对话</div>'
  }

  window.toggleHistory = function() {
    var drawer = document.getElementById('history-drawer')
    var tab = document.getElementById('history-tab')
    var open = drawer.classList.toggle('open')
    tab.classList.toggle('open')
    if (open) { renderHistory(); setTimeout(function(){ document.addEventListener('click', closeHistoryOnOutside, {once:true}) }, 100) }
  }
  function closeHistoryOnOutside(e) {
    var panel = document.getElementById('history-panel')
    if (panel && !panel.contains(e.target)) {
      document.getElementById('history-drawer').classList.remove('open')
      document.getElementById('history-tab').classList.remove('open')
    }
  }

  window.newConversation = function() {
    currentConvId = null; history = [];
    var chat = document.getElementById('chat-messages')
    chat.innerHTML = '<div class="msg-ai"><div class="avatar">CHEMAI · 教研助手</div><p>你好，老师。</p><p style="font-size:13px;color:#555;margin-top:4px;line-height:1.7">我能帮你：配平化学方程式 · 生成练习题 · 诊断学习障碍 · 搜索历年真题 · 模拟化学实验 · 生成学习报告</p></div>'
    renderHistory()
  }

  window.loadConversation = function(id) {
    var convs = getConversations(); var c = convs.find(function(x){return x.id===id})
    if (!c) return
    currentConvId = id; history = c.messages || []
    var chat = document.getElementById('chat-messages')
    chat.innerHTML = '<div class="msg-ai"><div class="avatar">CHEMAI · 教研助手</div><p>你好，老师。</p><p style="font-size:13px;color:#555;margin-top:4px;line-height:1.7">我能帮你：配平化学方程式 · 生成练习题 · 诊断学习障碍 · 搜索历年真题 · 模拟化学实验 · 生成学习报告</p></div>'
    history.forEach(function(m){
      var el = document.createElement('div')
      el.className = m.role === 'user' ? 'msg-user' : 'msg-ai'
      if (m.role === 'user') { el.textContent = m.content }
      else { el.innerHTML = '<div class="avatar">CHEMAI · 教研助手</div>' + renderMarkdown(m.content) }
      chat.appendChild(el)
    })
    renderHistory()
  }

  window.deleteConversation = function(id) {
    var convs = getConversations().filter(function(x){return x.id!==id})
    saveConversations(convs)
    if (currentConvId === id) { currentConvId = null; history = [] }
    renderHistory()
  }

  function saveCurrentConv() {
    var convs = getConversations()
    if (!currentConvId) { currentConvId = newConvId(); var c = {id:currentConvId,title:'',messages:[],updated:Date.now()}; convs.push(c) }
    var c = convs.find(function(x){return x.id===currentConvId})
    if (!c) { c = {id:currentConvId,title:'',messages:[],updated:Date.now()}; convs.push(c) }
    c.messages = history.slice()
    c.updated = Date.now()
    if (!c.title && history.length>0) {
      var firstUser = history.find(function(m){return m.role==='user'})
      if (firstUser) c.title = firstUser.content.substring(0,40)
    }
    saveConversations(convs)
    renderHistory()
  }

  window.setContext = function(ctx) {
    Object.assign(agentContext, ctx || {})
    renderContextBar()
  }
  window.clearContext = function() {
    agentContext = { class_id: '', class_name: '', exam_id: '', exam_name: '', student_id: '', student_name: '' }
    renderContextBar()
  }
  function renderContextBar() {
    var bar = document.getElementById('agent-context')
    if (!bar) return
    var visible = !!(agentContext.class_id || agentContext.exam_id || agentContext.student_id)
    bar.style.display = visible ? 'flex' : 'none'
    document.getElementById('ctx-class').textContent = agentContext.class_name || ''
    document.getElementById('ctx-class').style.display = agentContext.class_id ? '' : 'none'
    document.getElementById('ctx-exam').textContent = agentContext.exam_name || ''
    document.getElementById('ctx-exam').style.display = agentContext.exam_id ? '' : 'none'
    document.getElementById('ctx-student').textContent = agentContext.student_name || ''
    document.getElementById('ctx-student').style.display = agentContext.student_id ? '' : 'none'
  }

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
    if (isSending) return
    var input = document.getElementById('chat-input')
    var msg = text || input.value.trim()
    if (!msg) return
    if (!text) { input.value = ''; input.style.height = 'auto' }
    if (ChemAI.trackActivity) ChemAI.trackActivity('chat', msg.substring(0, 30))

    isSending = true
    var sendBtn = document.getElementById('chat-send')
    if (sendBtn) { sendBtn.disabled = true; sendBtn.style.opacity = '.5' }
    if (input) input.disabled = true

    addMsg('user', msg)
    history.push({ role: 'user', content: msg })

    // 思考状态进气泡
    var bubble = addMsg('ai', '<div class="think-status"><span class="dot"></span>思考中...</div><div class="think-dots"><span></span><span></span><span></span></div>')

    fetch('/api/agent/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona: 'teacher', message: msg, provider: 'deepseek', history: history.slice(0, -1) })
    }).then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status)
      return streamResponse(resp, bubble)
    }).catch(function (e) {
      bubble.innerHTML = '<span style="color:#b43c28">抱歉，请求失败: ' + e.message + '</span>'
      resetSendState()
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
              var st = bubble.querySelector('.think-status')
              if (st) st.innerHTML = '<span class="dot"></span>' + (evt.phase === 'thinking' ? '分析问题...' : evt.phase === 'executing' ? '正在执行...' : '正在回复...')
              break
            case 'text':
              if (!reply) bubble.innerHTML = ''  // 清除 think-orbit
              reply += evt.content
              // 方向2: 气体扩散 — raw streaming, markdown rendered at end
              bubble.innerHTML = wrapGasChars(reply)
              scrollBottom()
              break
            case 'tool_call':
              bubble.innerHTML = '<div class="think-status"><span class="dot"></span>调用工具: ' + evt.name + '</div>'
              toolCard = addToolCard(evt.name, 'running')
              break
            case 'tool_result':
              if (toolCard) updateToolCard(toolCard, evt)
              break
            case 'tool_error':
              if (toolCard) updateToolCard(toolCard, { success: false, result: { error: evt.error }, name: evt.name })
              else bubble.innerHTML = '<span style="color:#C53030">工具调用失败: ' + (evt.error || '未知错误') + '</span>'
              break
          }
        } catch (e) {}
      }
    }

    if (reply) {
      bubble.innerHTML = renderMarkdown(reply)
      history.push({ role: 'assistant', content: reply })
      saveCurrentConv()
    }
    resetSendState()
  }

  // 方向2: 气体扩散 — 每个字符 wrapped for staggered animation
  function wrapGasChars(text) {
    var result = ''
    var delay = 0
    for (var i = 0; i < text.length; i++) {
      var ch = text[i]
      if (ch === '\n') { result += '<br>'; continue }
      if (ch === ' ') { result += ' '; continue }
      result += '<span class="gas-char" style="animation-delay:' + (delay * .008).toFixed(3) + 's">' + escHtml_c(ch) + '</span>'
      delay++
      if (delay > 80) delay = 80  // cap delay at ~0.6s
    }
    return result
  }
  function escHtml(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }
  function escHtml_c(s) {
    if (s === '<') return '&lt;'; if (s === '>') return '&gt;'
    if (s === '&') return '&amp;'; if (s === '"') return '&quot;'
    return s
  }

  // ─── UI Helpers ───
  function addMsg(role, text) {
    var container = document.getElementById('chat-messages')
    var el = document.createElement('div')
    el.className = role === 'user' ? 'msg-user' : 'msg-ai'
    if (role === 'ai') {
      el.innerHTML = '<div class="avatar">CHEMAI · 教研助手</div>' + text
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
      '<span style="color:#b43c28">⚗</span>' +
      '<span style="font-weight:500">' + name + '</span>' +
      '<span style="color:#999;font-size:10px">运行中...</span>' +
      '</div><div class="tool-card-body"></div>'
    container.appendChild(card)
    scrollBottom()
    return card
  }

  function updateToolCard(card, evt) {
    var status = card.querySelector('.tool-card-header span:last-child')
    status.textContent = evt.success !== false ? '完成' : '失败'
    status.style.color = evt.success !== false ? '#2c6e49' : '#b43c28'
    var body = card.querySelector('.tool-card-body')
    var toolName = evt.name || evt.tool
    console.log('[updateToolCard] name:', evt.name, 'tool:', evt.tool, 'toolName:', toolName, 'has ChemRender:', !!window.ChemRender, 'has renderer:', !!(window.ChemRenderers||{})[toolName])
    var rendered = window.ChemRender ? window.ChemRender(toolName, evt.result) : '<pre>'+JSON.stringify(evt.result,null,2)+'</pre>'
    body.innerHTML = rendered
    body.classList.add('open')
    card.onclick = function () { body.classList.toggle('open') }
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

  function resetSendState() {
    isSending = false
    var sendBtn = document.getElementById('chat-send')
    var input = document.getElementById('chat-input')
    if (sendBtn) { sendBtn.disabled = false; sendBtn.style.opacity = '' }
    if (input) input.disabled = false
  }

  // ─── KaTeX 化学公式渲染 ───
  window.renderChemistry = function(text) {
    if (!text) return ''
    if (typeof katex === 'undefined') return escHtml(text)
    // 匹配 \ce{...} 或 化学方程式模式
    return text.replace(/\\ce\{([^}]+)\}/g, function(m, formula) {
      try { return katex.renderToString(formula, {throwOnError:false, trust:true, strict:false}) }
      catch(e) { return '<code>'+escHtml(formula)+'</code>' }
    })
    // 自动检测常见化学方程式模式
    .replace(/([A-Z][a-z]?\d*(?:[+\-]\d*)?(?:\s*[→=⇌＋+]\s*[A-Z][a-z]?\d*(?:[+\-]\d*)?)+)/g, function(m) {
      try {
        var eq = m.replace(/=/g, '=').replace(/→/g, '->').replace(/⇌/g, '<=>')
        return katex.renderToString('\\ce{'+eq+'}', {throwOnError:false, trust:true, strict:false})
      } catch(e) { return '<code>'+escHtml(m)+'</code>' }
    })
  }

  function renderMarkdown(text) {
    // 化学公式高亮：→ ↑ ↓ ⇌ Δ 等符号保留
    var html = text
      // 标题
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h3>$1</h3>')
      // 粗体/斜体
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // 行内代码
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // 化学方程式加粗红标记
      .replace(/([A-Z][a-z]?\d*(?:[+\-]\d*)?(?:\s*[→=⇌＋+]\s*[A-Z][a-z]?\d*(?:[+\-]\d*)?)+)/g, '<code>$1</code>')
      // 列表
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      // 连续 li 包进 ul
      .replace(/(<li>[\s\S]*?<\/li>)/g, function(m){ return '<ul>' + m + '</ul>' })
      // 数字列表
      .replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>')
      // 分隔线
      .replace(/^---$/gm, '<hr>')
      // 段落：连续两个换行
      .replace(/\n\n+/g, '</p><p>')
      // 单换行
      .replace(/\n/g, '<br>')
    return '<p>' + window.renderChemistry(html) + '</p>'
  }
})()
