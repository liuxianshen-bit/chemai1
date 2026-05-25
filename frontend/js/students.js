// 学生管理 + R6 详情弹窗
(function () {
  'use strict'
  var currentStudentId = null

  document.addEventListener('DOMContentLoaded', function () { loadStudents(); loadClassFilter() })

  function loadClassFilter() {
    fetch('/api/classes').then(function (r) { return r.json() }).then(function (d) {
      var sel = document.getElementById('student-class-filter')
      var list = d.classes || []
      list.forEach(function (c) { var o = document.createElement('option'); o.value = c.class_id; o.textContent = c.name; sel.appendChild(o) })
    })
  }

  window.loadStudents = function (kw) {
    var sf = document.getElementById('student-class-filter'), cls = sf ? sf.value : ''
    fetch('/api/users/students').then(function (r) { return r.json() }).then(function (d) {
      var list = d.students || (Array.isArray(d) ? d : [])
      if (kw) list = list.filter(function (s) { return s.name.indexOf(kw) >= 0 || s.student_id.indexOf(kw) >= 0 })
      if (cls) list = list.filter(function (s) { return s.class_id === cls })
      var el = document.getElementById('students-list'); if (!el) return
      el.innerHTML = list.length
        ? list.map(function (s) {
          var b = s.barrier_type || {}
          var dom = Object.keys(b).sort(function (a, b2) { return b[b2] - b[a] })[0] || ''
          return '<div class="card card-accent flex justify-between items-center cursor-pointer" onclick="showStudentDetail(\'' + s.student_id + '\')">' +
            '<div><span class="font-bold">' + s.name + '</span><span class="text-sm ml-2" style="color:#43474e;font-family:JetBrains Mono">' + s.student_id + '</span></div>' +
            '<div class="flex gap-2 items-center"><span class="tag tag-' + dom + '">' + (dom || '未诊断') + '</span><span class="text-sm" style="color:#74777f">练习:' + (s.exercises_completed || 0) + '次</span></div></div>'
        }).join('')
        : '<div class="empty-state"><span class="material-symbols-outlined text-4xl" style="color:#c4c6cf">group</span><p>暂无学生</p></div>'
    })
  }

  // R6: 详情弹窗
  window.showStudentDetail = function (sid) {
    currentStudentId = sid
    fetch('/api/users/students').then(function (r) { return r.json() }).then(function (d) {
      var list = d.students || (Array.isArray(d) ? d : [])
      var s = list.find(function (x) { return x.student_id === sid })
      if (!s) return

      document.getElementById('modal-name').textContent = s.name
      document.getElementById('modal-stats').innerHTML =
        '<div class="card text-center"><p class="text-2xl font-bold" style="color:#002045;font-family:Manrope">' + (s.exercises_completed || 0) + '</p><p class="text-xs" style="color:#43474e">练习次数</p></div>' +
        '<div class="card text-center"><p class="text-2xl font-bold" style="color:#13696a;font-family:Manrope">' + sid + '</p><p class="text-xs" style="color:#43474e">学号</p></div>' +
        '<div class="card text-center"><p class="text-2xl font-bold" style="color:#290068;font-family:Manrope">' + (s.status || '正常') + '</p><p class="text-xs" style="color:#43474e">状态</p></div>'

      var b = s.barrier_type || {}
      var dom = Object.keys(b).sort(function (a, b2) { return b[b2] - b[a] })[0] || '未诊断'
      document.getElementById('modal-barrier').innerHTML =
        '<p class="text-sm" style="color:#43474e">主导类型: <span class="tag tag-' + dom + '">' + dom + '</span></p>'

      fetch('/api/report/student/' + sid).then(function (r) { return r.json() }).then(function (rd) {
        var el = document.getElementById('modal-report')
        if (!el) return
        el.innerHTML = rd
          ? '<p>最近考试: ' + (rd.exam_name || '无') + ' | 得分: ' + (rd.your_score || 0) + ' | 均分: ' + (rd.class_avg_score || 0) + '</p><p class="mt-1">' + (rd.summary || '') + '</p>'
          : '<p>暂无学情数据</p>'
      }).catch(function () {
        var el = document.getElementById('modal-report'); if (el) el.innerHTML = '<p>暂无学情数据</p>'
      })

      var modal = document.getElementById('student-modal'); if (modal) modal.style.display = 'flex'
    })
  }

  window.closeStudentModal = function () { var m = document.getElementById('student-modal'); if (m) m.style.display = 'none'; currentStudentId = null }
  window.genPlanForModal = function () {
    if (!currentStudentId) return
    fetch('/api/diagnosis/learning-plan/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_id: currentStudentId, barrier_type: 'concept', weak_knowledge_points: [] }) })
      .then(function (r) { return r.json() }).then(function () { alert('学习计划已生成!') }).catch(function (e) { alert('失败: ' + e.message) })
  }
})()
