/**
 * ChemAI — 全局应用逻辑
 * 认证检查 / 侧边栏渲染 / fetch token 注入 / 页面路由
 */
(function () {
  'use strict'

  // ─── 认证检查 ───
  var user = getUser()
  if (!user) { window.location.href = '/login.html'; return }

  // ─── fetch 拦截：自动注入 token ───
  var _fetch = window.fetch
  window.fetch = function (url, opts) {
    opts = opts || {}
    var u = typeof url === 'string' ? url : (url.url || '')
    if (u.indexOf('/api/') >= 0) {
      var token = getToken()
      if (token) {
        opts.headers = opts.headers || {}
        if (opts.headers instanceof Headers) {
          if (!opts.headers.has('Authorization'))
            opts.headers = Object.assign({ Authorization: 'Bearer ' + token }, Object.fromEntries(opts.headers.entries()))
        } else if (!opts.headers.Authorization && !opts.headers['Authorization']) {
          opts.headers['Authorization'] = 'Bearer ' + token
        }
      }
    }
    return _fetch.call(this, url, opts)
  }

  // ─── 侧边栏渲染 ───
  function renderSidebar(active) {
    var nav = [
      { id: 'chat', sym: 'Ai', icon: 'psychology', label: 'AI 教研助手', href: '/' },
      { id: 'ocr',  sym: 'Oc', icon: 'document_scanner', label: '答题卡识别', href: '/pages/ocr.html' },
      { id: 'exam', sym: 'Ex', icon: 'assignment', label: '考试工作台', href: '/pages/exam-v2.html' },
      { id: 'diagnosis', sym: 'Dx', icon: 'health_and_safety', label: '障碍诊断', href: '/pages/diagnosis.html' },
      { id: 'teacher', sym: 'Td', icon: 'bar_chart', label: '学情面板', href: '/pages/teacher.html' },
      { id: 'students', sym: 'St', icon: 'group', label: '学生管理', href: '/pages/students.html' },
    ]
    var html = nav.map(function (n) {
      var cls = n.id === active ? 'elem-nav active' : 'elem-nav'
      return '<a class="' + cls + '" href="' + n.href + '">' +
        '<span class="sym">' + n.sym + '</span>' +
        n.label + '</a>'
    }).join('')

    var sidebar = document.getElementById('sidebar-nav')
    if (sidebar) sidebar.innerHTML = html
  }

  // ─── 用户信息渲染 ───
  function renderUser() {
    var el = document.getElementById('user-name')
    if (el) el.textContent = user.name || '教师'
    var el2 = document.getElementById('user-role')
    if (el2) el2.textContent = user.school || '智辅化学'
  }

  // ─── 辅助函数 ───
  function getUser() {
    try { return JSON.parse(sessionStorage.getItem('chemai_user')) } catch (e) { return null }
  }
  function getToken() {
    var u = getUser(); return u ? u.token : ''
  }

  // ─── 最近活动追踪 ───
  function getActivities() {
    try { return JSON.parse(sessionStorage.getItem('chemai_activities') || '[]') } catch (e) { return [] }
  }
  function trackActivity(type, summary) {
    var acts = getActivities()
    acts.unshift({ type: type, summary: summary, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
    if (acts.length > 5) acts.length = 5
    sessionStorage.setItem('chemai_activities', JSON.stringify(acts))
  }
  function renderActivities() {
    var acts = getActivities()
    var container = document.getElementById('recent-activity')
    var list = document.getElementById('recent-activity-list')
    if (!container || !list) return
    if (!acts.length) { container.style.display = 'none'; return }
    container.style.display = 'block'
    var icons = { chat: 'psychology', exam: 'assignment', diagnosis: 'health_and_safety', ocr: 'document_scanner', students: 'group', plan: 'description' }
    list.innerHTML = acts.map(function (a) {
      return '<div class="flex items-center gap-2 text-xs" style="padding:4px 8px;color:rgba(255,255,255,.4)">' +
        '<span class="material-symbols-outlined text-[14px]" style="color:rgba(255,255,255,.3)">' + (icons[a.type] || 'circle') + '</span>' +
        '<span style="flex:1;color:rgba(255,255,255,.5);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + escHtmlS(a.summary) + '</span>' +
        '<span style="font-family:JetBrains Mono;color:rgba(255,255,255,.35)">' + (a.time || '') + '</span>' +
        '</div>'
    }).join('')
  }
  function escHtmlS(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }

  // ─── 暴露到全局 ───
  window.ChemAI = {
    user: user,
    renderSidebar: renderSidebar,
    renderUser: renderUser,
    getToken: getToken,
    getUser: getUser,
    trackActivity: trackActivity,
    logout: function () { sessionStorage.removeItem('chemai_user'); window.location.href = '/login.html' }
  }

  // ─── 页面加载时自动渲染 ───
  document.addEventListener('DOMContentLoaded', function () {
    renderUser()
    // 根据路径判断 active
    var path = window.location.pathname
    var active = 'chat'
    if (path.indexOf('ocr') >= 0) active = 'ocr'
    else if (path.indexOf('exam') >= 0) active = 'exam'
    else if (path.indexOf('diagnosis') >= 0) active = 'diagnosis'
    else if (path.indexOf('students') >= 0) active = 'students'
    renderSidebar(active)
    renderActivities()
  })
})()
