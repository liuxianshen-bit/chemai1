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
      { id: 'chat', icon: 'psychology', label: 'AI 教研助手', href: '/' },
      { id: 'ocr', icon: 'document_scanner', label: '答题卡识别', href: '/pages/ocr.html' },
      { id: 'exam', icon: 'assignment', label: '考试工作台', href: '/pages/exam.html' },
      { id: 'diagnosis', icon: 'health_and_safety', label: '障碍诊断', href: '/pages/diagnosis.html' },
      { id: 'students', icon: 'group', label: '学生管理', href: '/pages/students.html' },
    ]
    var html = nav.map(function (n) {
      var cls = n.id === active ? 'sidebar-link active' : 'sidebar-link'
      return '<a class="' + cls + '" href="' + n.href + '">' +
        '<span class="material-symbols-outlined">' + n.icon + '</span>' +
        n.label + '</a>'
    }).join('')

    // 渲染侧边栏导航
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

  // ─── 暴露到全局 ───
  window.ChemAI = {
    user: user,
    renderSidebar: renderSidebar,
    renderUser: renderUser,
    getToken: getToken,
    getUser: getUser,
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
    else if (path.indexOf('questions') >= 0) active = 'questions'
    else if (path.indexOf('diagnosis') >= 0) active = 'diagnosis'
    else if (path.indexOf('report') >= 0) active = 'report'
    else if (path.indexOf('panel') >= 0) active = 'panel'
    else if (path.indexOf('students') >= 0) active = 'students'
    renderSidebar(active)
  })
})()
