// 学生管理 — 搜索/筛选/分页 + 详情弹窗（学情+趋势+诊断+操作）
(function () {
  'use strict'
  var allStudents = []
  var pageSize = 20
  var currentPage = 1
  var currentStudentId = null
  var currentStudent = null

  document.addEventListener('DOMContentLoaded', function () {
    loadClassFilter()
    loadAllStudents()
  })

  function loadClassFilter() {
    fetch('/api/classes').then(function (r) { return r.json() }).then(function (d) {
      var sel = document.getElementById('student-class-filter')
      var list = d.classes || []
      list.forEach(function (c) { var o = document.createElement('option'); o.value = c.class_id; o.textContent = c.name; sel.appendChild(o) })
    })
  }

  function loadAllStudents() {
    fetch('/api/users/students').then(function (r) { return r.json() }).then(function (d) {
      allStudents = d.students || (Array.isArray(d) ? d : [])
      filterAndRender()
    })
  }

  // ═══════════════════════════════════════════════
  // 6.1: 搜索 + 筛选 + 分页
  // ═══════════════════════════════════════════════
  window.filterAndRender = function () {
    var kw = (document.getElementById('student-search').value || '').toLowerCase()
    var cls = document.getElementById('student-class-filter').value

    var filtered = allStudents.filter(function (s) {
      if (kw && !(s.name.toLowerCase().includes(kw) || (s.student_id || '').toLowerCase().includes(kw))) return false
      if (cls && s.class_id !== cls) return false
      return true
    })

    var totalPages = Math.ceil(filtered.length / pageSize) || 1
    currentPage = Math.min(currentPage, totalPages)
    var start = (currentPage - 1) * pageSize
    var page = filtered.slice(start, start + pageSize)

    var el = document.getElementById('students-list')
    el.innerHTML = page.length
      ? page.map(function (s) { return studentCard(s) }).join('')
      : '<div class="empty-state"><span class="material-symbols-outlined text-4xl" style="color:#c4c6cf">group</span><p>暂无匹配学生</p></div>'

    // Pagination
    var pEl = document.getElementById('pagination')
    pEl.innerHTML = totalPages > 1
      ? '<button class="btn-secondary btn-sm" ' + (currentPage <= 1 ? 'disabled' : '') + ' onclick="goPage(' + (currentPage - 1) + ')">上一页</button>' +
        '<span class="text-sm" style="padding:6px 12px;color:#43474e">第 ' + currentPage + '/' + totalPages + ' 页 (' + filtered.length + ' 人)</span>' +
        '<button class="btn-secondary btn-sm" ' + (currentPage >= totalPages ? 'disabled' : '') + ' onclick="goPage(' + (currentPage + 1) + ')">下一页</button>'
      : '<span class="text-sm" style="color:#74777f;display:block;text-align:center">共 ' + filtered.length + ' 名学生</span>'
  }

  window.goPage = function (p) { currentPage = p; filterAndRender() }

  function studentCard(s) {
    var raw = s.barrier_type
    var b = (typeof raw === 'object' && raw !== null) ? raw : {}
    var dom = Object.keys(b).sort(function (a, b2) { return b[b2] - b[a] })[0] || ''
    var domLabel = { concept: '概念理解', reading: '审题障碍', expression: '表述障碍' }[dom] || (dom || '未诊断')
    return '<div class="student-row" onclick="openDetail(\'' + esc(s.student_id) + '\')">' +
      '<div class="flex-1"><span class="font-medium">' + escHtml(s.name) + '</span>' +
      '<span class="text-xs ml-2" style="font-family:JetBrains Mono;color:#74777f">' + escHtml(s.student_id) + '</span></div>' +
      '<span class="tag mr-2 tag-' + dom + '">' + domLabel + '</span>' +
      '<span class="text-sm" style="color:#43474e">练习: ' + (s.exercises_completed || 0) + '次</span>' +
      '</div>'
  }

  // ═══════════════════════════════════════════════
  // 6.2: 详情弹窗
  // ═══════════════════════════════════════════════
  window.openDetail = function (sid) {
    currentStudentId = sid
    currentStudent = allStudents.find(function (s) { return s.student_id === sid })
    if (!currentStudent) return

    document.getElementById('md-name').textContent = currentStudent.name + ' · ' + currentStudent.student_id

    // 6.3: 学情概览
    var ex = currentStudent.exercises_completed || 0
    var status = currentStudent.status || 'active'
    var raw2 = currentStudent.barrier_type
    var b = (typeof raw2 === 'object' && raw2 !== null) ? raw2 : {}
    var dom = Object.keys(b).sort(function (a, b2) { return b[b2] - b[a] })[0] || '未诊断'

    document.getElementById('md-stats').innerHTML =
      statCard('exercise', ex, '练习次数', '#002045') +
      statCard('school', status, '状态', status === 'approved' ? '#2F855A' : '#e6a817') +
      statCard('psychology', dom, '主导障碍', '#290068') +
      statCard('functions', (b[dom] ? Math.round(b[dom] * 100) + '%' : '--'), '置信度', '#13696a')

    // 6.5: 障碍诊断
    fetch('/api/diagnosis/plan/' + sid).then(function (r) { return r.json() }).then(function (d) {
      var data = d.data || {}
      var bt = data.barrier_type || b
      var wkp = data.weak_knowledge_points || []
      var intervention = data.recommended_intervention || ''
      var html = '<div class="flex flex-wrap gap-3 mb-2">' +
        '<span class="tag tag-concept">概念理解: ' + Math.round((bt.concept || 0) * 100) + '%</span>' +
        '<span class="tag tag-reading">审题障碍: ' + Math.round((bt.reading || 0) * 100) + '%</span>' +
        '<span class="tag tag-expression">表述障碍: ' + Math.round((bt.expression || 0) * 100) + '%</span>' +
        '</div>'
      if (wkp.length) html += '<p class="text-xs mb-1" style="color:#74777f">弱知识点: ' + wkp.map(function (k) { return '<span class="tag tag-medium">' + escHtml(k) + '</span>' }).join(' ') + '</p>'
      if (intervention) html += '<p class="text-xs" style="color:#43474e">' + escHtml(intervention) + '</p>'
      document.getElementById('md-barrier').innerHTML = html
    }).catch(function () {
      document.getElementById('md-barrier').innerHTML = '<p class="text-sm" style="color:#74777f">暂无诊断数据</p>'
    })

    // 6.4: 进步趋势 — 获取历史诊断数据
    fetch('/api/diagnosis/history/' + sid + '?limit=5').then(function (r) { return r.json() }).then(function (d) {
      var history = d.history || []
      if (!history.length) {
        document.getElementById('md-trend').innerHTML = '<p class="text-sm" style="color:#74777f">暂无历史数据</p>'
        return
      }
      var labels = history.map(function (h) { return (h.exam_name || '').substring(0, 6) })
      var values = history.map(function (h) { return Math.round((h.accuracy || 0) * 100) })
      var maxVal = Math.max.apply(null, values.concat([1]))
      var minVal = Math.min.apply(null, values.concat([100]))
      var range = Math.max(maxVal - minVal, 1)

      var svgW = 600, svgH = 160, padL = 40, padR = 20, padT = 10, padB = 30
      var pw = svgW - padL - padR, ph = svgH - padT - padB
      var points = values.map(function (v, i) {
        return (padL + i * pw / Math.max(values.length - 1, 1)) + ',' + (padT + ph - (v - minVal) / range * ph)
      }).join(' ')

      var svg = '<svg width="100%" viewBox="0 0 ' + svgW + ' ' + svgH + '" style="max-width:600px">' +
        // Grid lines
        '<line x1="' + padL + '" y1="' + padT + '" x2="' + padL + '" y2="' + (padT + ph) + '" stroke="#e4e2de" stroke-width="1"/>' +
        '<line x1="' + padL + '" y1="' + (padT + ph) + '" x2="' + (padL + pw) + '" y2="' + (padT + ph) + '" stroke="#e4e2de" stroke-width="1"/>'
      // Y axis labels — dynamic from data range
      var yStep = Math.max(Math.ceil(range / 4), 1)
      var yStart = Math.floor(minVal / yStep) * yStep
      var yEnd = Math.ceil(maxVal / yStep) * yStep
      for (var y = yStart; y <= yEnd; y += yStep) {
        var yPos = padT + ph - (y - minVal) / range * ph
        svg += '<text x="' + (padL - 8) + '" y="' + (yPos + 3) + '" text-anchor="end" font-size="9" fill="#74777f" font-family="JetBrains Mono">' + y + '</text>'
        if (y > minVal && y < maxVal) svg += '<line x1="' + padL + '" y1="' + yPos + '" x2="' + (padL + pw) + '" y2="' + yPos + '" stroke="#f0ede8" stroke-width="1" stroke-dasharray="3,3"/>'
      }
      // Line
      svg += '<polyline points="' + points + '" fill="none" stroke="#13696a" stroke-width="2" stroke-linejoin="round"/>'
      // Dots + labels
      values.forEach(function (v, i) {
        var cx = padL + i * pw / Math.max(values.length - 1, 1)
        var cy = padT + ph - (v - minVal) / range * ph
        svg += '<circle cx="' + cx + '" cy="' + cy + '" r="4" fill="#fff" stroke="#13696a" stroke-width="2"/>'
        svg += '<text x="' + cx + '" y="' + (svgH - 6) + '" text-anchor="middle" font-size="9" fill="#43474e">' + (labels[i] || '') + '</text>'
        svg += '<text x="' + cx + '" y="' + (cy - 10) + '" text-anchor="middle" font-size="10" font-weight="600" fill="#13696a" font-family="Manrope">' + v + '%</text>'
      })
      svg += '</svg>'
      document.getElementById('md-trend').innerHTML = svg
    }).catch(function () {
      document.getElementById('md-trend').innerHTML = '<p class="text-sm" style="color:#74777f">加载趋势失败</p>'
    })

    // 6.6: 操作按钮
    document.getElementById('md-actions').innerHTML =
      '<button class="btn-primary btn-sm" onclick="openTransfer()"><span class="material-symbols-outlined text-[16px]">swap_horiz</span> 转班</button>' +
      '<button class="btn-secondary btn-sm" onclick="resetPassword()"><span class="material-symbols-outlined text-[16px]">lock_reset</span> 重置密码</button>' +
      '<button class="btn-teal btn-sm" onclick="genPlanFromStudents()"><span class="material-symbols-outlined text-[16px]">psychology</span> 生成学习计划</button>'

    openModal('modal-detail')
  }

  window.closeDetail = function () { closeModal('modal-detail'); currentStudentId = null; currentStudent = null }

  function statCard(icon, value, label, color) {
    return '<div class="card text-center"><span class="material-symbols-outlined text-[20px]" style="color:' + color + '">' + icon + '</span><p class="text-lg font-bold mt-1" style="color:' + color + ';font-family:Manrope">' + value + '</p><p class="text-xs" style="color:#43474e">' + label + '</p></div>'
  }

  // ═══════════════════════════════════════════════
  // 6.6: 转班 / 重置密码 / 生成计划
  // ═══════════════════════════════════════════════
  window.openTransfer = function () {
    if (!currentStudent) return
    document.getElementById('tf-student-name').textContent = currentStudent.name + ' (' + currentStudent.student_id + ')'
    // Load classes
    var sel = document.getElementById('tf-class')
    // Keep first option, clear rest
    while (sel.options.length > 1) sel.remove(1)
    fetch('/api/classes').then(function (r) { return r.json() }).then(function (d) {
      var list = d.classes || []
      list.forEach(function (c) {
        if (c.class_id !== currentStudent.class_id) {
          var o = document.createElement('option'); o.value = c.class_id; o.textContent = c.name; sel.appendChild(o)
        }
      })
    })
    openModal('modal-transfer')
  }

  window.closeTransfer = function () { closeModal('modal-transfer') }

  window.confirmTransfer = function () {
    var cls = document.getElementById('tf-class').value
    if (!cls) { alert('请选择目标班级'); return }
    fetch('/api/users/student/' + currentStudentId + '/transfer', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_class_id: cls })
    }).then(function (r) { return r.json() }).then(function (d) {
      if (d.success) { alert(d.message); closeTransfer(); closeDetail(); loadAllStudents() }
      else { alert('转班失败: ' + d.message) }
    }).catch(function (e) { alert('转班失败: ' + e.message) })
  }

  window.resetPassword = function () {
    if (!confirm('确定将 ' + currentStudent.name + ' 的密码重置为默认密码 123456？')) return
    fetch('/api/users/student/' + currentStudentId + '/reset-password', { method: 'POST' })
      .then(function (r) { return r.json() }).then(function (d) { alert(d.message) })
      .catch(function (e) { alert('重置失败: ' + e.message) })
  }

  window.genPlanFromStudents = function () {
    fetch('/api/diagnosis/learning-plan/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: currentStudentId, barrier_type: 'concept', weak_knowledge_points: [] })
    }).then(function (r) { return r.json() }).then(function () { alert('学习计划已生成!') })
      .catch(function (e) { alert('生成失败: ' + e.message) })
  }

  // ═══════════════════════════════════════════════
  // Helpers
  // ═══════════════════════════════════════════════
  function openModal(id) { var el = document.getElementById(id); if (el) el.style.display = 'flex' }
  function closeModal(id) { var el = document.getElementById(id); if (el) el.style.display = 'none' }
  function escHtml(s) { if (!s) return ''; return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;') }
  function esc(s) { if (!s) return ''; return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'") }
})()
