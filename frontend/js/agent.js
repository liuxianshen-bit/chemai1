/**
 * ChemAI Agent Chat — SSE 流式对话
 */
(function () {
  'use strict'
  var history = []
  var isSending = false
  var currentConvId = sessionStorage.getItem('chemai_active_cid') || null
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
    sessionStorage.removeItem('chemai_active_cid');
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

    // Ensure conversation_id exists and is persisted
    if (!currentConvId) {
      currentConvId = sessionStorage.getItem('chemai_active_cid') || newConvId()
    }
    sessionStorage.setItem('chemai_active_cid', currentConvId)

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

    fetch('/api/agent/chat/langgraph/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona: 'teacher', message: msg, provider: 'deepseek', conversation_id: currentConvId, history: history.slice(0, -1) })
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
            case 'component':
              sessionStorage.removeItem('chemai_navigate')
              if (evt.component === 'exam-workbench') renderExamWorkbench(evt.params || {}, bubble)
              else if (evt.component === 'diagnosis') renderDiagnosis(evt.params || {}, bubble)
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
        } catch (e) { console.error('SSE event error:', e) }
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
          // Persist conversation_id before navigating away
          if (currentConvId) sessionStorage.setItem('chemai_active_cid', currentConvId)
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

  // ─── Inline Exam Workbench Panel (Full Interactive) ───
  function renderExamWorkbench(params, bubble) {
    var preKps = (params.knowledge_points || []).join('、')
    var preDiff = params.difficulty || 'medium'
    var preTypes = params.types || [{val:'single_choice',active:true,qty:3}]
    var preVariant = params.variant_source || ''
    var preFolder = params.set_name || ''

    var html = '<div class="inline-exam-panel">'+
      '<div class="inline-exam-header" style="font-weight:700;margin-bottom:10px;font-size:15px;border-bottom:2px solid #b43c28;padding-bottom:8px">考试工作台</div>'+
      '<div style="margin-bottom:12px"><div style="font-size:12px;color:#888;margin-bottom:4px">题型与数量</div><div class="inline-exam-types"></div></div>'+
      '<div style="margin-bottom:12px"><span style="font-size:12px;color:#888">难度</span> <select class="inline-exam-diff" style="padding:4px 8px;border:1px solid #ddd;border-radius:4px;font-size:13px"><option value="easy"'+(preDiff==='easy'?' selected':'')+'>容易</option><option value="medium"'+(preDiff==='medium'?' selected':'')+'>中等</option><option value="hard"'+(preDiff==='hard'?' selected':'')+'>偏难</option></select></div>'+
      '<div style="margin-bottom:12px;border-top:1px solid #eee;padding-top:10px"><div style="font-size:12px;color:#888;margin-bottom:4px">知识点 <span style="font-weight:400">（搜索并点击选中）</span></div><div class="inline-exam-kps-active" style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px;min-height:20px"></div><input class="inline-exam-kp-search" placeholder="搜索知识点..." style="width:100%;padding:6px 10px;border:1px solid #ddd;border-radius:4px;font-size:13px;box-sizing:border-box;margin-bottom:6px"><div class="inline-exam-kps-list" style="display:flex;flex-wrap:wrap;gap:4px;max-height:100px;overflow-y:auto"></div></div>'+
      '<div style="margin-bottom:12px;border-top:1px solid #eee;padding-top:10px"><label style="font-size:13px;cursor:pointer"><input type="checkbox" class="inline-exam-use-variant" style="margin-right:4px"'+(preVariant?' checked':'')+'>基于真题生成变种题</label><div class="inline-exam-variant-info" style="margin-top:4px;font-size:12px;color:#b43c28">'+(preVariant?'当前蓝本: '+escHtml(preVariant):'')+'</div><button class="inline-exam-btn sm inline-exam-variant-browse" style="margin-top:4px;display:'+(preVariant?'inline-block':'none')+'">浏览真题蓝本</button></div>'+
      '<div style="margin-bottom:12px;border-top:1px solid #eee;padding-top:10px"><div style="font-size:12px;color:#888;margin-bottom:4px">保存到</div><select class="inline-exam-folder" style="padding:4px 8px;border:1px solid #ddd;border-radius:4px;font-size:13px;min-width:200px"><option value="">自动创建</option></select><button class="inline-exam-btn sm inline-exam-new-folder" style="margin-left:6px">+ 新建</button></div>'+
      '<div class="inline-exam-actions" style="margin-bottom:10px"><button class="inline-exam-btn primary inline-exam-gen-btn">AI 出题</button></div>'+
      '<div class="inline-exam-questions" style="display:none"></div><div class="inline-exam-status" style="font-size:13px;color:#888"></div></div>'

    bubble.insertAdjacentHTML('beforeend', html)

    // Post-render: populate interactive controls
    var panel = bubble.querySelector('.inline-exam-panel:last-child')
    if (!panel) return

    panel._preKps = preKps; panel._variantSource = preVariant; panel._variantQid = ''

    // Types
    var typesContainer = panel.querySelector('.inline-exam-types')
    var typeDefs = [{val:'single_choice',label:'选择题',active:false,qty:3},{val:'fill_blank',label:'填空题',active:false,qty:2},{val:'calculation',label:'计算题',active:false,qty:1},{val:'experiment',label:'实验题',active:false,qty:1},{val:'inference',label:'推断题',active:false,qty:1}]
    preTypes.forEach(function(pt){ var m=typeDefs.find(function(t){return t.val===pt.val}); if(m){m.active=pt.active;m.qty=pt.qty||m.qty} })
    function _renderTypes(){ typesContainer.innerHTML = typeDefs.map(function(t,i){ return '<span class="inline-exam-type-chip" data-idx="'+i+'" style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;margin:2px;border:1.5px solid '+(t.active?'#b43c28':'#ddd')+';border-radius:14px;cursor:pointer;font-size:12px;background:'+(t.active?'rgba(180,60,40,.06)':'#fff')+';color:'+(t.active?'#b43c28':'#888')+'">'+(t.active?'●':'○')+' '+t.label+(t.active?' <input type="number" min="1" max="10" value="'+t.qty+'" style="width:36px;padding:2px 4px;border:1px solid #ddd;border-radius:3px;font-size:12px;text-align:center" onclick="event.stopPropagation()">':'')+'</span>' }).join('') }
    _renderTypes()
    typesContainer.addEventListener('click',function(e){ var chip=e.target.closest('.inline-exam-type-chip'); if(!chip)return; var t=typeDefs[parseInt(chip.dataset.idx)]; t.active=!t.active; _renderTypes() })
    typesContainer.addEventListener('change',function(e){ if(e.target.tagName==='INPUT'){ var chip=e.target.closest('.inline-exam-type-chip'); typeDefs[parseInt(chip.dataset.idx)].qty=parseInt(e.target.value)||1 } })

    // KPs
    fetch('/api/knowledge/list').then(function(r){return r.json()}).then(function(data){
      var allKps=(data.knowledge_points||data.data||[]).map(function(k){return typeof k==='string'?{name:k,active:false}:{name:k.name||k,active:false}})
      if(preKps){preKps.split('、').forEach(function(pk){var m=allKps.find(function(k){return k.name===pk});if(m)m.active=true})}
      panel._kps=allKps; _renderKps()
    }).catch(function(){})
    var kpSearch=panel.querySelector('.inline-exam-kp-search'); kpSearch.addEventListener('input',function(){_renderKps()})
    function _renderKps(){
      var kps=panel._kps||[], s=kpSearch.value.toLowerCase()
      var active=panel.querySelector('.inline-exam-kps-active'), list=panel.querySelector('.inline-exam-kps-list')
      var aKps=kps.filter(function(k){return k.active})
      active.innerHTML=aKps.length?aKps.map(function(k){return '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;background:rgba(180,60,40,.08);border:1px solid #b43c28;border-radius:12px;font-size:12px;color:#b43c28;cursor:pointer" data-kp="'+escHtml(k.name)+'">'+escHtml(k.name)+'<span style="font-size:14px">&times;</span></span>'}).join(''):'<span style="font-size:12px;color:#bbb">未选择</span>'
      active.querySelectorAll('span[data-kp]').forEach(function(c){c.addEventListener('click',function(){var m=kps.find(function(k){return k.name===c.dataset.kp});if(m)m.active=false;_renderKps()})})
      var filtered=kps.filter(function(k){return!k.active&&(!s||k.name.toLowerCase().includes(s))})
      list.innerHTML=filtered.slice(0,30).map(function(k){return '<span style="display:inline-block;padding:3px 8px;border:1.5px solid #ddd;border-radius:12px;font-size:12px;cursor:pointer;color:#555;white-space:nowrap" data-kp="'+escHtml(k.name)+'">'+escHtml(k.name)+'</span>'}).join('')
      list.querySelectorAll('span[data-kp]').forEach(function(c){c.addEventListener('click',function(){var m=kps.find(function(k){return k.name===c.dataset.kp});if(m)m.active=true;_renderKps()})})
    }

    // Folders
    fetch('/api/exam-bank/exam-sets').then(function(r){return r.json()}).then(function(data){
      var sets=(data.data&&data.data.exam_sets)||data.exam_sets||[]
      var sel=panel.querySelector('.inline-exam-folder'); sets.forEach(function(s){sel.innerHTML+='<option value="'+s.set_id+'">'+escHtml(s.name)+' ('+(s.question_count||0)+')</option>'})
    }).catch(function(){})

    // Generate
    panel.querySelector('.inline-exam-gen-btn').addEventListener('click',function(){
      var active=typeDefs.filter(function(t){return t.active}), st=panel.querySelector('.inline-exam-status'), qa=panel.querySelector('.inline-exam-questions')
      if(!active.length){st.textContent='请至少选择一种题型';return}
      var diff=panel.querySelector('.inline-exam-diff').value
      var kps=(panel._kps||[]).filter(function(k){return k.active}).map(function(k){return k.name})
      if(!kps.length)kps=['高中化学综合']
      var fs=panel.querySelector('.inline-exam-folder'), fid=fs.value||'auto', fn=fs.selectedOptions&&fs.selectedOptions[0]?fs.selectedOptions[0].textContent.replace(/\s*\(\d+\)\s*$/,''):'自动创建'
      st.textContent='生成中...'; qa.style.display='none'
      var pending=active.length, all=[]
      active.forEach(function(t){fetch('/api/question/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({knowledge_points:kps,difficulty:diff,quantity:t.qty,question_types:[t.val]})}).then(function(r){return r.json()}).then(function(d){(d.questions||[]).forEach(function(q){q._typeLabel=t.val;q._saved=false});all=all.concat(d.questions||[]);pending--;if(pending===0){st.textContent='';qa.style.display='block';_renderQs(all,qa,fid,fn)}}).catch(function(){pending--;if(pending===0)st.textContent='生成失败'})})
    })

    function _renderQs(qs,container,folderId,folderName){
      var h='<div style="margin-top:12px;font-size:13px">共 '+qs.length+' 题 · '+escHtml(folderName)+'</div>'
      qs.forEach(function(q,i){var o=(q.options||[]).map(function(o,j){return '<div>'+String.fromCharCode(65+j)+'. '+escHtml(o)+'</div>'}).join('')
        h+='<div class="inline-exam-qcard" data-idx="'+i+'" style="border:1px solid #eee;border-radius:6px;padding:10px;margin:8px 0"><div><b>'+(i+1)+'.</b> '+(typeof renderChemistry==='function'?renderChemistry(q.content||''):escHtml(q.content||''))+'</div>'+(q.options?'<div style="margin:8px 0 0 20px;font-size:13px">'+o+'</div>':'')+'<div style="margin-top:6px;font-size:12px;color:#999">答案: <span style="color:#b43c28">'+escHtml(q.answer||'')+'</span></div><div style="margin-top:6px"><button onclick="ChemAI._saveQ(this,'+i+')" class="inline-exam-btn sm">保存</button><button onclick="ChemAI._delQ(this,'+i+')" class="inline-exam-btn sm">删除</button></div></div>'})
      h+='<div style="margin-top:10px"><button onclick="ChemAI._saveAll(this)" class="inline-exam-btn primary">全部保存</button><button onclick="ChemAI._redo(this)" class="inline-exam-btn">全部重出</button><button onclick="ChemAI._done(this)" class="inline-exam-btn">完成</button></div>'
      container.innerHTML=h; container._qs=qs; container._fid=folderId; container._fn=folderName
    }

    // Variant
    panel.querySelector('.inline-exam-use-variant').addEventListener('change',function(){panel.querySelector('.inline-exam-variant-browse').style.display=this.checked?'inline-block':'none'})
    panel.querySelector('.inline-exam-variant-browse').addEventListener('click',function(){
      var ov=document.createElement('div'); ov.className='inline-exam-vb-overlay'; ov.style.cssText='position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.3);z-index:9999;display:flex;align-items:center;justify-content:center'
      ov.innerHTML='<div style="background:#fff;border-radius:8px;padding:16px;max-width:600px;max-height:80vh;overflow-y:auto;width:90%"><div style="font-weight:700;margin-bottom:10px">选择真题蓝本</div><div class="ivb-content" style="font-size:13px">加载中...</div><button style="margin-top:10px;padding:4px 16px;border:1px solid #ddd;border-radius:4px;cursor:pointer;float:right">关闭</button></div>'
      document.body.appendChild(ov); ov.querySelector('button').addEventListener('click',function(){document.body.removeChild(ov)}); ov.addEventListener('click',function(e){if(e.target===ov)document.body.removeChild(ov)})
      fetch('/api/exam-bank/papers').then(function(r){return r.json()}).then(function(data){var ps=(data.papers||data.data||[]),c=ov.querySelector('.ivb-content')
        c.innerHTML='<div style="font-size:12px;color:#888;margin-bottom:8px">点击试卷浏览题目，再点击题目选为蓝本</div>'+ps.slice(0,50).map(function(p){return '<div class="ivb-paper" style="padding:6px 8px;margin:2px 0;border:1px solid #eee;border-radius:4px;cursor:pointer;font-size:12px" data-r="'+escHtml(p.region||'')+'" data-y="'+(p.year||'')+'">'+escHtml(p.source||p.name||'')+' · '+(p.year||'')+' ('+(p.question_count||p.total||'?')+'题)</div>'}).join('')
        c.querySelectorAll('.ivb-paper').forEach(function(el){el.addEventListener('click',function(){c.innerHTML='加载中...'
          fetch('/api/exam-bank/historical?region='+encodeURIComponent(el.dataset.r)+'&year='+encodeURIComponent(el.dataset.y)+'&page_size=30').then(function(r){return r.json()}).then(function(qd){var qs=(qd.questions||qd.data||[])
            c.innerHTML='<div style="font-size:12px;color:#888;margin-bottom:8px">点击题目选为蓝本</div>'+qs.map(function(q,i){return '<div class="ivb-q" data-qid="'+(q.exam_id||q.question_id||'')+'" style="padding:6px 8px;margin:2px 0;border:1px solid #eee;border-radius:4px;cursor:pointer;font-size:12px"><b>#'+(i+1)+'</b> '+escHtml((q.content||'').substring(0,80))+'</div>'}).join('')
            c.querySelectorAll('.ivb-q').forEach(function(qel){qel.addEventListener('click',function(){panel._variantQid=qel.dataset.qid;panel._variantSource=(el.dataset.r||'')+' · #'+(Array.from(qel.parentNode.children).indexOf(qel)+1);panel.querySelector('.inline-exam-variant-info').textContent='当前蓝本: '+panel._variantSource;document.body.removeChild(ov)})})
          }).catch(function(){c.innerHTML='加载失败'})
        })})
      }).catch(function(){ov.querySelector('.ivb-content').innerHTML='加载失败'})
    })

    // New folder
    panel.querySelector('.inline-exam-new-folder').addEventListener('click',function(){var n=prompt('请输入新题库名称：');if(!n)return
      fetch('/api/exam-bank/exam-sets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,region:'',year:null,source:'agent',description:''})}).then(function(r){return r.json()}).then(function(d){if(d.success){var s=panel.querySelector('.inline-exam-folder');s.innerHTML+='<option value="'+d.exam_set.set_id+'" selected>'+escHtml(n)+' (0)</option>'}}).catch(function(){})})
  }

  // ─── Shared panel helpers ───
  window.ChemAI._saveQ = function(btn, idx) {
    var c = btn.closest('.inline-exam-questions'), q = (c._qs || [])[idx]
    if (!q || q._saved) return
    var body = JSON.stringify({set_id: c._fid, questions: [{content: q.content, options: q.options || [], answer: q.answer || '', knowledge_points: q.knowledge_points || [], difficulty: q.difficulty || 'medium'}]})
    fetch('/api/exam-bank/import-questions', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: body})
      .then(function(r) { return r.json() }).then(function(d) { if (d.success) { q._saved = true; btn.textContent = '已保存'; btn.disabled = true; btn.style.opacity = '.4' } })
  }
  window.ChemAI._delQ = function(btn, idx) { var c = btn.closest('.inline-exam-qcard'); if (c) c.style.display = 'none' }
  window.ChemAI._saveAll = function(btn) {
    var c = btn.closest('.inline-exam-questions'), qs = (c._qs || []).filter(function(q) { return !q._saved })
    if (!qs.length) return
    var body = JSON.stringify({set_id: c._fid, questions: qs.map(function(q) { return {content: q.content, options: q.options || [], answer: q.answer || '', knowledge_points: q.knowledge_points || [], difficulty: q.difficulty || 'medium'} })})
    fetch('/api/exam-bank/import-questions', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: body})
      .then(function(r) { return r.json() }).then(function(d) { if (d.success) { qs.forEach(function(q) { q._saved = true }); btn.textContent = '已保存'; btn.disabled = true; btn.style.opacity = '.4' } })
  }
  window.ChemAI._redo = function(btn) { var p = btn.closest('.inline-exam-panel'); p.querySelector('.inline-exam-questions').style.display = 'none'; p.querySelector('.inline-exam-status').textContent = ''; p.querySelector('.inline-exam-gen-btn').click() }
  window.ChemAI._done = function(btn) { var p = btn.closest('.inline-exam-panel'), c = p.querySelector('.inline-exam-questions'), qs = c._qs || []; p.querySelector('.inline-exam-status').textContent = '已完成'; sendMessage('出题完成：共生成' + qs.length + '道题，已保存' + qs.filter(function(q) { return q._saved }).length + '道。') }

  // ─── Inline Diagnosis Panel ───
  function renderDiagnosis(params, bubble) {
    var h='<div class="inline-diag-panel" style="border:1px solid #eee;border-radius:8px;padding:14px;margin:8px 0">'
    h+='<div style="font-weight:700;margin-bottom:10px;font-size:15px">学情诊断: '+escHtml(params.student_name||params.student_id||'')+'</div>'
    if(params.dominant_barrier){h+='<div style="margin-bottom:8px;font-size:13px">主导障碍: <b>'+escHtml(params.dominant_barrier)+'</b> · 完成练习: '+(params.exercises_completed||0)+'</div>'}
    var barrier=params.barrier_distribution||{}
    if(Object.keys(barrier).length){
      h+='<div class="inline-diag-chart" style="width:100%;height:200px;margin:8px 0"></div>'
      h+='<div class="inline-diag-fallback" style="display:none">'
      Object.keys(barrier).forEach(function(k){h+='<div style="margin:4px 0;font-size:13px">'+escHtml(k)+': <b>'+Math.round((barrier[k]||0)*100)+'%</b></div>'})
      h+='</div>'
    }
    h+='<div style="margin-top:8px"><button onclick="ChemAI._diagToExam(this)" class="inline-exam-btn primary">针对障碍出题练习</button></div></div>'
    bubble.insertAdjacentHTML('beforeend',h)

    // ECharts
    var chartDiv=bubble.querySelector('.inline-diag-chart:last-child')
    if(chartDiv&&typeof echarts!=='undefined'){
      try{var chart=echarts.init(chartDiv);chart.setOption({tooltip:{},xAxis:{type:'category',data:Object.keys(barrier)},yAxis:{type:'value',max:1},series:[{type:'bar',data:Object.values(barrier),itemStyle:{color:'#b43c28'}}]})}catch(e){chartDiv.style.display='none';bubble.querySelector('.inline-diag-fallback:last-child').style.display='block'}
    }else if(chartDiv){chartDiv.style.display='none';bubble.querySelector('.inline-diag-fallback:last-child').style.display='block'}
  }

  window.ChemAI._diagToExam = function(btn){sendMessage('针对学习障碍出题练习')}
})()
