/**
 * ChemAI Agent Chat — SSE 流式对话
 */
(function () {
  'use strict'
  var history = []
  var isSending = false
  var currentConvId = null
  var agentContext = { class_id: '', class_name: '', exam_id: '', exam_name: '', student_id: '', student_name: '' }
  var _toolStartTime = 0

  // ─── 历史对话管理 ───
  function getConversations() {
    try { return JSON.parse(localStorage.getItem('chemai_convs') || '[]') } catch(e) { return [] }
  }
  function saveConversations(convs) { localStorage.setItem('chemai_convs', JSON.stringify(convs)) }
  function newConvId() { return 'c' + Date.now() }

  function renderHistory() {
    // Now rendered in the sidebar via refreshSidebarConvs()
    refreshSidebarConvs()
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
    refreshSidebarConvs()
  }

  function refreshSidebarConvs() {
    var el = document.getElementById('conv-list')
    if (!el) return
    var convs = getConversations()
    convs.sort(function(a, b) { return (b.updated || 0) - (a.updated || 0) })
    var html = ''
    convs.forEach(function(c) {
      html += '<div class="history-item' + (c.id === currentConvId ? ' active' : '') + '" onclick="loadConversation(\'' + c.id + '\')">' +
        '<span class="title">' + (c.title || '新对话') + '</span>' +
        '<button class="del" onclick="event.stopPropagation();deleteConversation(\'' + c.id + '\')" title="删除">×</button></div>'
    })
    el.innerHTML = html || '<div style="padding:20px 12px;text-align:center;color:#999;font-size:13px">暂无对话记录</div>'
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

  // ─── 化学式实时格式化 ───
  var SUB = ['₀','₁','₂','₃','₄','₅','₆','₇','₈','₉']
  var SUP = ['⁰','¹','²','³','⁴','⁵','⁶','⁷','⁸','⁹']
  function subDigits(s) { var r=''; for (var i=0;i<s.length;i++) r+=SUB[s[i]]; return r }
  function superDigits(s) { var r=''; for (var i=0;i<s.length;i++) r+=SUP[s[i]]; return r }

  function formatChemicalText(text) {
    var result = '', i = 0, elemCount = 0
    text = text.replace(/-->/g, '→').replace(/->/g, '→')

    function resetWord() { elemCount = 0 }
    function isSep(ch) { return !ch || /[\s+=→\+\-\(\)]/.test(ch) }

    while (i < text.length) {
      var ch = text[i]

      // = between words → arrow
      if (ch === '=' && (i===0 || text[i-1]===' ') && (i+1>=text.length || text[i+1]===' ')) {
        result += '→'; i++; resetWord(); continue
      }
      // + or - preceded by space → separator (not charge), reset word
      if ((ch === '+' || ch === '-') && (i===0 || text[i-1]===' ')) {
        result += ch; i++; resetWord(); continue
      }

      // Element symbol
      if (/[A-Z]/.test(ch)) {
        var elem = ch; i++
        if (i < text.length && /[a-z]/.test(text[i])) { elem += text[i]; i++ }
        elemCount++

        // Digits after element
        if (i < text.length && /[0-9]/.test(text[i])) {
          var num = ''; while (i < text.length && /[0-9]/.test(text[i])) { num += text[i]; i++ }
          // Followed by charge sign at end of compound?
          if (i < text.length && /[+-]/.test(text[i]) && (i+1>=text.length || /[\s+=→]/.test(text[i+1]))) {
            var chargeSign = text[i]
            // Single element + short number → all charge: Fe3+ → Fe³⁺
            if (elemCount === 1 && parseInt(num) <= 3) {
              result += elem + superDigits(num) + (chargeSign==='+'?'⁺':'⁻'); i++; resetWord(); continue
            }
            // Multi-element: last digit ≤3 → split into subscript + charge: SO42- → SO₄²⁻
            if (elemCount > 1 && num.length > 1 && parseInt(num[num.length-1]) <= 3) {
              result += elem + subDigits(num.slice(0,-1)) + superDigits(num.slice(-1)) + (chargeSign==='+'?'⁺':'⁻'); i++; resetWord(); continue
            }
            // Subscript + separate charge: MnO4- → MnO₄⁻, NH4+ → NH₄⁺
            result += elem + subDigits(num) + (chargeSign==='+'?'⁺':'⁻'); i++; resetWord(); continue
          }
          result += elem + subDigits(num); continue
        }

        // Element directly + charge: Na+ → Na⁺
        if (i < text.length && /[+-]/.test(text[i]) && (i+1>=text.length || /[\s+=→]/.test(text[i+1]))) {
          result += elem + (text[i]==='+'?'⁺':'⁻'); i++; resetWord(); continue
        }
        result += elem; continue
      }

      // Standalone number + charge: 2e-, 3+
      if (/[0-9]/.test(ch)) {
        var n = ''; while (i < text.length && /[0-9]/.test(text[i])) { n += text[i]; i++ }
        if (i < text.length && /[+-]/.test(text[i]) && (i+1>=text.length || /[\s+=→]/.test(text[i+1]))) {
          result += superDigits(n) + (text[i]==='+'?'⁺':'⁻'); i++; resetWord(); continue
        }
        result += n; continue
      }

      // ) + digits → )₃
      if (ch === ')' && i+1 < text.length && /[0-9]/.test(text[i+1])) {
        result += ')'; i++; var pn = ''; while (i < text.length && /[0-9]/.test(text[i])) { pn += text[i]; i++ }
        result += subDigits(pn); continue
      }

      if (ch === ' ' || ch === '+' || ch === '→') resetWord()
      result += ch; i++
    }
    return result
  }

  function updateChemPreview() {
    var input = document.getElementById('chat-input')
    var preview = document.getElementById('chem-preview')
    if (!input || !preview) return
    var raw = input.value.trim()
    if (!raw) { preview.className = 'chem-preview'; preview.textContent = ''; return }
    var formatted = formatChemicalText(raw)
    if (formatted === raw) { preview.className = 'chem-preview'; preview.textContent = ''; return }
    preview.textContent = formatted
    preview.className = 'chem-preview show'
  }

  // ─── 事件绑定 ───
  document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('chat-input')
    if (input) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
        autoResize(input)
      })
      input.addEventListener('input', function () { autoResize(input); updateChemPreview() })
    }

    // Suggestion chips — fill input with template, let user complete
    document.querySelectorAll('.chip[data-prompt]').forEach(function (c) {
      c.addEventListener('click', function () {
        var input = document.getElementById('chat-input')
        input.value = c.dataset.prompt
        input.focus()
        autoResize(input)
        updateChemPreview()
      })
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
    var preview = document.getElementById('chem-preview')
    var msg = text || (preview && preview.textContent) || input.value.trim()
    if (!msg) return
    if (!text) { input.value = ''; input.style.height = 'auto'; if (preview) { preview.className = 'chem-preview'; preview.textContent = '' } }
    if (ChemAI.trackActivity) ChemAI.trackActivity('chat', msg.substring(0, 30))

    isSending = true
    var sendBtn = document.getElementById('chat-send')
    if (sendBtn) { sendBtn.disabled = true; sendBtn.style.opacity = '.5' }
    if (input) input.disabled = true

    // Show status bar
    var stBar = document.getElementById('agent-status')
    if (stBar) { stBar.style.display = 'flex' }
    var stTool = document.getElementById('status-tool')
    if (stTool) stTool.textContent = '分析中...'
    var stTime = document.getElementById('status-time')
    if (stTime) stTime.textContent = ''
    _toolStartTime = Date.now()

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
    var buffer = '', reply = '', toolCards = []

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
              var phaseLabels = {thinking:'分析问题...', executing:'正在执行...', reply:'正在回复...', planning:'生成计划中...'}
              if (st) st.innerHTML = '<span class="dot"></span>' + (phaseLabels[evt.phase] || evt.phase)
              break
            case 'plan_summary':
              bubble.innerHTML += addPlanCard(evt)
              scrollBottom()
              break
            case 'plan_progress':
              updatePlanCard(evt)
              break
            case 'step':
              var st2 = bubble.querySelector('.think-status')
              var labels = {search_exam_bank:'搜索真题', generate_questions:'AI出题', diagnose_barrier:'障碍诊断', chemistry_tutor:'智能辅导', simulate_experiment:'模拟实验', weekly_report:'生成周报', import_exam_paper:'导入试卷', assign_adaptive_practice:'布置练习', balance_equation:'配平审核', web_search:'联网搜索'}
              var label = labels[evt.skill] || evt.skill
              if (st2) st2.innerHTML = '<span class="dot"></span>第 ' + (evt.current || '?') + ' 步：' + label
              break
            case 'text':
              if (!reply) bubble.textContent = ''
              reply += evt.content
              bubble.textContent = reply
              scrollBottom()
              break
            case 'tool_call':
              bubble.innerHTML = '<div class="think-status"><span class="dot"></span>调用工具: ' + evt.name + '</div>'
              var card = addToolCard(evt.name, 'running')
              toolCards.push(card)
              // Update status bar
              var stTool2 = document.getElementById('status-tool')
              if (stTool2) stTool2.textContent = evt.name
              break
            case 'tool_result':
              var lastCard = toolCards[toolCards.length - 1]
              if (lastCard) updateToolCard(lastCard, evt)
              break
            case 'tool_error':
              var lastErrCard = toolCards[toolCards.length - 1]
              if (lastErrCard) updateToolCard(lastErrCard, { success: false, result: { error: evt.error }, name: evt.name })
              else bubble.innerHTML = '<span style="color:#C53030">工具调用失败: ' + (evt.error || '未知错误') + '</span>'
              break
            case 'navigate':
              var nav = {page: evt.page, params: evt.params || {}, data: {}, actions: []}
              sessionStorage.setItem('chemai_navigate', JSON.stringify(nav))
              break
            case 'populate':
              try {
                var navData = JSON.parse(sessionStorage.getItem('chemai_navigate') || '{}')
                if (!navData.data) navData.data = {}
                navData.data[evt.target] = evt.data
                sessionStorage.setItem('chemai_navigate', JSON.stringify(navData))
              } catch(e) {}
              break
            case 'action':
              try {
                var navAct = JSON.parse(sessionStorage.getItem('chemai_navigate') || '{}')
                if (!navAct.actions) navAct.actions = []
                navAct.actions.push({action: evt.action, payload: evt.payload})
                sessionStorage.setItem('chemai_navigate', JSON.stringify(navAct))
              } catch(e) {}
              break
            case 'error':
              var errHtml = '<div style="color:#b43c28;padding:8px 0;font-size:13px">' +
                '<span style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#999">' + (evt.code || 'ERROR') + '</span><br>' +
                escHtml(evt.message || '未知错误') + '</div>'
              if (evt.recoverable) {
                errHtml += '<button class="btn btn-sm" onclick="ChemAI.retryLastMessage()" style="margin-top:6px;font-size:12px">重试</button>'
              }
              bubble.innerHTML = errHtml
              resetSendState()
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
    // Check if agent wants to navigate to another page
    var navigateTo = sessionStorage.getItem('chemai_navigate')
    if (navigateTo) {
      try {
        var nav = JSON.parse(navigateTo)
        if (nav.page) {
          setTimeout(function() {
            window.location.href = '/pages/' + nav.page + '.html'
          }, 500)
        }
      } catch(e) {}
    }
    resetSendState()
  }

  function escHtml(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }

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

    // Auto-parse JSON string results into objects for renderers
    var data = evt.result
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch(e) { /* keep as string */ }
    }

    try {
      var rendered = window.ChemRender ? window.ChemRender(toolName, data) : '<pre>'+JSON.stringify(data,null,2)+'</pre>'
      body.innerHTML = rendered
    } catch(e) {
      console.error('[updateToolCard] render error:', e)
      body.innerHTML = '<pre style="color:#C53030;font-size:11px">渲染失败: ' + escHtml(String(e.message || e)) + '</pre>'
    }
    body.classList.add('open')
    card.onclick = function () { body.classList.toggle('open') }
  }

  // ─── Plan Card ───
  var _planSteps = []  // Track plan step states

  function addPlanCard(plan) {
    _planSteps = plan.steps.map(function(s) {
      return {step: s.step, skill: s.skill, description: s.description, status: 'pending'}
    })
    var html = '<div class="plan-card" id="plan-card">' +
      '<div class="plan-card-header" style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:16px;font-weight:600;margin-bottom:10px">' +
        '📋 ' + escHtml(plan.goal || '执行计划') +
        '<span style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#999;margin-left:8px">' + plan.total_steps + ' 步</span>' +
      '</div>'
    plan.steps.forEach(function(s, i) {
      html += '<div class="plan-step" id="plan-step-' + i + '" style="display:flex;align-items:center;gap:10px;padding:6px 0;font-size:13px">' +
        '<span class="plan-step-num" style="width:24px;height:24px;border-radius:50%;border:1.5px solid rgba(0,0,0,.15);display:flex;align-items:center;justify-content:center;font-family:\'JetBrains Mono\',monospace;font-size:11px;flex-shrink:0">' + s.step + '</span>' +
        '<span style="flex:1">' + escHtml(s.description) + '</span>' +
        '<span class="plan-step-status" style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#999">等待中</span>' +
        '</div>'
    })
    html += '<div class="plan-card-summary" style="display:none;font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#2c6e49;padding:4px 0"></div>'
    html += '</div>'
    return html
  }

  function updatePlanCard(progress) {
    var idx = (progress.current_step || 1) - 1
    var stepEl = document.getElementById('plan-step-' + idx)
    if (!stepEl) return
    var numEl = stepEl.querySelector('.plan-step-num')
    var statusEl = stepEl.querySelector('.plan-step-status')
    if (progress.status === 'running') {
      numEl.style.background = '#b43c28'; numEl.style.color = '#fff'; numEl.style.borderColor = '#b43c28'
      statusEl.textContent = '执行中...'; statusEl.style.color = '#b43c28'
      _planSteps[idx].status = 'running'
    } else if (progress.status === 'completed') {
      numEl.style.background = '#2c6e49'; numEl.style.color = '#fff'; numEl.style.borderColor = '#2c6e49'
      numEl.textContent = '✓'
      statusEl.textContent = '完成'; statusEl.style.color = '#2c6e49'
      _planSteps[idx].status = 'completed'
    } else if (progress.status === 'failed') {
      numEl.style.background = '#b43c28'; numEl.style.color = '#fff'; numEl.style.borderColor = '#b43c28'
      numEl.textContent = '✗'
      statusEl.textContent = '失败'; statusEl.style.color = '#b43c28'
      _planSteps[idx].status = 'failed'
    }
    // Check if all done
    if (_planSteps.every(function(s) { return s.status === 'completed' || s.status === 'failed' })) {
      setTimeout(function() {
        var card = document.getElementById('plan-card')
        if (!card) return
        var summary = card.querySelector('.plan-card-summary')
        var done = _planSteps.filter(function(s){return s.status==='completed'}).length
        var total = _planSteps.length
        summary.textContent = done + '/' + total + ' 步骤已完成'
        summary.style.display = ''
        card.querySelectorAll('.plan-step').forEach(function(el) { el.style.display = 'none' })
        card.onclick = function() {
          var collapsed = card.querySelector('.plan-card-summary').style.display !== 'none'
          card.querySelectorAll('.plan-step').forEach(function(el) { el.style.display = collapsed ? '' : 'none' })
          card.querySelector('.plan-card-summary').style.display = collapsed ? 'none' : ''
        }
      }, 2000)
    }
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
    // Update status bar with elapsed time
    var stBar2 = document.getElementById('agent-status')
    if (stBar2 && _toolStartTime) {
      var elapsed = ((Date.now() - _toolStartTime) / 1000).toFixed(1)
      var stTime2 = document.getElementById('status-time')
      if (stTime2) stTime2.textContent = elapsed + 's'
      setTimeout(function () { if (stBar2) stBar2.style.display = 'none' }, 3000)
    }
    _toolStartTime = 0
  }

  // ─── Markdown 渲染（自包含解析器 + KaTeX） ───
  var _latexBlocks = []

  function renderMarkdown(text) {
    if (!text) return ''
    _latexBlocks = []

    // Step 1: protect LaTeX / chemistry before parsing
    var safe = text
      .replace(/\$\$([\s\S]*?)\$\$/g, function(m, f) { _latexBlocks.push({t:'d',f:f}); return '\x00L' + (_latexBlocks.length-1) + '\x00' })
      .replace(/\\\[([\s\S]*?)\\\]/g, function(m, f) { _latexBlocks.push({t:'d',f:f}); return '\x00L' + (_latexBlocks.length-1) + '\x00' })
      .replace(/\\\(([\s\S]*?)\\\)/g, function(m, f) { _latexBlocks.push({t:'i',f:f}); return '\x00l' + (_latexBlocks.length-1) + '\x00' })
      .replace(/\$([^$]+?)\$/g, function(m, f) { _latexBlocks.push({t:'i',f:f}); return '\x00l' + (_latexBlocks.length-1) + '\x00' })
      .replace(/\\ce\{([^}]+)\}/g, function(m, f) { _latexBlocks.push({t:'c',f:f}); return '\x00c' + (_latexBlocks.length-1) + '\x00' })

    // Step 2: line-by-line parser: tables first, then other elements
    var lines = safe.split('\n')
    var html = '', i = 0
    while (i < lines.length) {
      var line = lines[i], trimmed = line.trim()

      // Skip empty
      if (!trimmed) { i++; continue }

      // Table: if current line is |...| and next line is separator |---|
      if (/^\|.*\|$/.test(trimmed)) {
        var next = i + 1 < lines.length ? lines[i + 1].trim() : ''
        if (/^\|[\s\-:|]+\|$/.test(next)) {
          html += parseTable(lines, i)
          while (i < lines.length && lines[i].trim() && /^\|.*\|$/.test(lines[i].trim())) i++
          continue
        }
      }

      // Fenced code block ```
      if (/^```/.test(trimmed)) {
        html += '<pre><code>'
        i++
        while (i < lines.length && !/^```/.test(lines[i].trim())) {
          html += escHtml(lines[i]) + '\n'
          i++
        }
        html += '</code></pre>'
        i++
        continue
      }

      // Heading
      var hm = trimmed.match(/^(#{1,6})\s+(.+)$/)
      if (hm) {
        var lvl = hm[1].length
        html += '<h' + lvl + '>' + renderInline(hm[2]) + '</h' + lvl + '>'
        i++; continue
      }

      // Horizontal rule
      if (/^(---|\*\*\*|___)\s*$/.test(trimmed)) {
        html += '<hr>'
        i++; continue
      }

      // Blockquote
      if (trimmed.startsWith('> ')) {
        html += '<blockquote><p>' + renderInline(trimmed.slice(2)) + '</p></blockquote>'
        i++; continue
      }

      // Unordered list — group adjacent
      if (/^[\-\*\+]\s+/.test(trimmed)) {
        html += '<ul>'
        while (i < lines.length && /^[\-\*\+]\s+/.test(lines[i].trim())) {
          html += '<li>' + renderInline(lines[i].trim().replace(/^[\-\*\+]\s+/, '')) + '</li>'
          i++
        }
        html += '</ul>'
        continue
      }

      // Ordered list — group adjacent
      if (/^\d+\.\s+/.test(trimmed)) {
        html += '<ol>'
        while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
          html += '<li>' + renderInline(lines[i].trim().replace(/^\d+\.\s+/, '')) + '</li>'
          i++
        }
        html += '</ol>'
        continue
      }

      // Paragraph
      html += '<p>' + renderInline(trimmed) + '</p>'
      i++
    }

    // Step 3: restore KaTeX placeholders
    if (typeof katex !== 'undefined') {
      html = html.replace(/\x00L(\d+)\x00/g, function(m, idx) {
        var b = _latexBlocks[parseInt(idx)]
        try { return katex.renderToString(b.f, {throwOnError:false, displayMode:true, trust:true, strict:false}) }
        catch(e) { return '<code>' + escHtml(b.f) + '</code>' }
      })
      html = html.replace(/\x00l(\d+)\x00/g, function(m, idx) {
        var b = _latexBlocks[parseInt(idx)]
        try { return katex.renderToString(b.f, {throwOnError:false, displayMode:false, trust:true, strict:false}) }
        catch(e) { return '<code>' + escHtml(b.f) + '</code>' }
      })
      html = html.replace(/\x00c(\d+)\x00/g, function(m, idx) {
        var b = _latexBlocks[parseInt(idx)]
        try { return katex.renderToString('\\ce{' + b.f + '}', {throwOnError:false, displayMode:false, trust:true, strict:false}) }
        catch(e) { return '<code>\\ce{' + escHtml(b.f) + '}</code>' }
      })
    } else {
      html = html.replace(/\x00[Ll](\d+)\x00/g, function(m, i) { return '<code>' + escHtml(_latexBlocks[parseInt(i)].f) + '</code>' })
      html = html.replace(/\x00c(\d+)\x00/g, function(m, i) { return '<code>\\ce{' + escHtml(_latexBlocks[parseInt(i)].f) + '}</code>' })
    }

    // Step 4: auto-detect chemical equations in text nodes
    if (typeof katex !== 'undefined') {
      html = html.replace(/>([^<]+)</g, function(m, text) {
        return '>' + text.replace(/([A-Z][a-z]?\d*(?:[+\-]\d*)?(?:\s*[→=⇌＋+]\s*[A-Z][a-z]?\d*(?:[+\-]\d*)?)+)/g, function(eq) {
          try {
            var fixed = eq.replace(/=/g, '=').replace(/→/g, '->').replace(/⇌/g, '<=>')
            return katex.renderToString('\\ce{' + fixed + '}', {throwOnError:false, trust:true, strict:false})
          } catch(e) { return '<code>' + escHtml(eq) + '</code>' }
        }) + '<'
      })
    }

    return html
  }

  // ─── Table parser ───
  function parseTable(lines, startIdx) {
    var headerLine = lines[startIdx].trim()
    // Remove leading/trailing |, split by |
    var headers = splitTableRow(headerLine)
    var html = '<table><thead><tr>'
    for (var h = 0; h < headers.length; h++) {
      html += '<th>' + renderInline(headers[h].trim()) + '</th>'
    }
    html += '</tr></thead><tbody>'
    // Skip separator line
    var i = startIdx + 2
    while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) {
      var cells = splitTableRow(lines[i].trim())
      html += '<tr>'
      for (var c = 0; c < Math.min(cells.length, headers.length); c++) {
        html += '<td>' + renderInline(cells[c].trim()) + '</td>'
      }
      html += '</tr>'
      i++
    }
    html += '</tbody></table>'
    return html
  }

  function splitTableRow(line) {
    // "| a | b | c |" → ["a", "b", "c"]
    var parts = line.split('|')
    // First and last may be empty (leading/trailing |)
    if (parts[0].trim() === '') parts.shift()
    if (parts.length && parts[parts.length-1].trim() === '') parts.pop()
    return parts
  }

  // ─── Inline renderer (bold/italic/code) ───
  function renderInline(text) {
    return escHtml(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
  }

  // 保留 renderChemistry 作为外部 API
  window.renderChemistry = function(text) {
    if (!text) return ''
    if (typeof katex === 'undefined') return escHtml(text)
    return text.replace(/\\ce\{([^}]+)\}/g, function(m, formula) {
      try { return katex.renderToString(formula, {throwOnError:false, trust:true, strict:false}) }
      catch(e) { return '<code>'+escHtml(formula)+'</code>' }
    })
  }
})()
