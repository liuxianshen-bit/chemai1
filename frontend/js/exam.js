// 考试工作台 — 三Tab: 考试 / 题库 / 历史真题 (懒加载)
(function () {
  'use strict'
  var historyPage = 1, historyLoading = false

  document.addEventListener('DOMContentLoaded', function () {
    loadClasses(); loadExams(); loadHistorical(true)
  })

  // ─── Tab 切换 ───
  window.switchExamTab = function (t) {
    ['exams', 'bank', 'history'].forEach(function (x) {
      var p = document.getElementById('panel-' + x)
      var b = document.getElementById('tab-' + x)
      if (p) p.style.display = x === t ? 'block' : 'none'
      if (b) { b.style.borderColor = x === t ? '#002045' : 'transparent'; b.style.color = x === t ? '#002045' : '#74777f' }
    })
  }

  function loadClasses() {
    fetch('/api/classes').then(function (r) { return r.json() }).then(function (d) {
      var sel = document.getElementById('exam-class')
      var list = d.classes || []
      list.forEach(function (c) { var o = document.createElement('option'); o.value = c.class_id; o.textContent = c.name; sel.appendChild(o) })
    })
  }

  // ─── Tab 1: 我的考试 ───
  window.loadExams = function () {
    fetch('/api/classes').then(function (r) { return r.json() }).then(function (d) {
      var list = d.classes || []; var exams = []
      Promise.all(list.map(function (c) { return fetch('/api/exam/list/' + c.class_id).then(function (r) { return r.json() }).catch(function () { return [] }) }))
        .then(function (results) {
          results.forEach(function (r, i) { if (r && r.length) r.forEach(function (e) { e.class_name = list[i].name; exams.push(e) }) })
          var el = document.getElementById('exam-list')
          if (!el) return
          el.innerHTML = exams.length
            ? exams.map(function (e) { return card('assignment', e.name, e.class_name + ' · ' + e.total_students + '人参试') }).join('')
            : empty('assignment', '暂无考试')
        })
    })
  }

  window.createExam = function () {
    var name = document.getElementById('exam-name').value
    var cls = document.getElementById('exam-class').value
    if (!name) { alert('请输入考试名称'); return }
    if (!cls) { alert('请选择班级'); return }
    fetch('/api/exam/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name, class_id: cls, total_students: 34 }) })
      .then(function (r) { return r.json() }).then(function () { alert('创建成功!'); loadExams() }).catch(function (e) { alert('失败: ' + e.message) })
  }

  // ─── Tab 2: 题库 ───
  window.toggleAiPanel = function () { var p = document.getElementById('ai-gen-panel'); if (p) p.style.display = p.style.display === 'none' ? 'block' : 'none' }
  window.searchQuestions = function () { loadBank(document.getElementById('q-keyword').value) }
  window.aiGenerate = function () {
    var kps = document.getElementById('q-kps').value
    var diff = document.getElementById('q-diff').value
    var qty = document.getElementById('q-qty').value
    fetch('/api/question/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ knowledge_points: kps.split(','), difficulty: diff, quantity: parseInt(qty) || 5 }) })
      .then(function (r) { return r.json() }).then(function (d) { showAiResult(d.questions || [], 'AI 生成 (' + d.total + '题)') }).catch(function (e) { alert('生成失败: ' + e.message) })
  }

  function loadBank(kw) {
    var url = '/api/exam-bank/historical?limit=50' + (kw ? '&keyword=' + encodeURIComponent(kw) : '')
    fetch(url).then(function (r) { return r.json() }).then(function (d) {
      var list = d.questions || [], el = document.getElementById('q-list'); if (!el) return
      el.innerHTML = list.length
        ? list.map(function (q) { return qCard(q) }).join('')
        : empty('menu_book', '暂无题目')
    })
  }

  function showAiResult(qs, title) {
    var h = '<h3 class="text-lg font-bold mt-4 mb-2" style="font-family:Manrope">' + title + '</h3>'
    qs.forEach(function (q, i) { h += qCard(q, i + 1) })
    var el = document.getElementById('q-list'); if (el) el.insertAdjacentHTML('afterbegin', h)
  }

  function qCard(q, num) {
    var n = num ? '<p class="font-bold">#' + num + '</p>' : ''
    var opts = (q.options || []).map(function (o) { return '<span class="text-sm mr-3" style="font-family:JetBrains Mono">' + o + '</span>' }).join('')
    var tags = (q.knowledge_points || []).map(function (k) { return '<span class="tag tag-medium">' + k + '</span>' }).join('')
    return '<div class="card card-accent"><span class="tag tag-' + q.difficulty + '" style="float:right">' + q.difficulty + '</span>' +
      n + '<p class="text-sm mt-1">' + q.content + '</p><div class="mt-2">' + opts + '</div>' +
      '<div class="flex gap-2 mt-2">' + tags + '</div></div>'
  }

  // ─── Tab 3: 历史真题 (懒加载分页, 30条/页) ───
  window.loadHistorical = function (reset) {
    if (reset) { historyPage = 1; var el = document.getElementById('h-list'); if (el) el.innerHTML = '' }
    if (historyLoading) return
    historyLoading = true

    var ke = document.getElementById('h-keyword'), kw = ke ? ke.value : ''
    var ye = document.getElementById('h-year'), yr = ye ? ye.value : ''
    var de = document.getElementById('h-diff'), df = de ? de.value : ''

    var url = '/api/exam-bank/historical?limit=30&offset=' + ((historyPage - 1) * 30) +
      (kw ? '&keyword=' + encodeURIComponent(kw) : '') + (yr ? '&year=' + yr : '') + (df ? '&difficulty=' + df : '')

    var listEl = document.getElementById('h-list'); if (!listEl) { historyLoading = false; return }
    if (historyPage === 1) listEl.innerHTML = '<div class="empty-state"><div class="progress-bar" style="width:200px"><div class="progress-fill pulse" style="width:60%"></div></div><p class="mt-2">加载真题中...</p></div>'

    fetch(url).then(function (r) { return r.json() }).then(function (d) {
      var list = d.questions || []
      if (historyPage === 1) listEl.innerHTML = ''
      if (list.length === 0 && historyPage === 1) { listEl.innerHTML = empty('history_edu', '暂无真题'); historyLoading = false; return }
      if (list.length > 0) {
        listEl.insertAdjacentHTML('beforeend', list.map(function (q) { return qCard(q) }).join(''))
        if (list.length === 30) listEl.insertAdjacentHTML('beforeend', '<div class="text-center mt-4"><button class="btn-secondary text-sm" onclick="loadHistorical()">加载更多 (已加载 ' + (historyPage * 30) + ' 条)</button></div>')
        historyPage++
      }
      historyLoading = false
    }).catch(function () { historyLoading = false })

    // 初始化年份和难度下拉
    var sy = document.getElementById('h-year')
    if (sy && !sy.hasChildNodes()) for (var y = 2025; y >= 2008; y--) { var o = document.createElement('option'); o.value = y; o.textContent = y; sy.appendChild(o) }
  }

  // ─── Helpers ───
  function card(icon, title, desc) {
    return '<div class="card card-accent"><div class="flex justify-between items-center"><div>' +
      '<p class="font-bold">' + title + '</p><p class="text-sm mt-1" style="color:#43474e">' + desc + '</p></div></div></div>'
  }
  function empty(icon, msg) {
    return '<div class="empty-state"><span class="material-symbols-outlined text-4xl" style="color:#c4c6cf">' + icon + '</span><p class="mt-2">' + msg + '</p></div>'
  }
})()
