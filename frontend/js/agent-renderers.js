/**
 * ChemAI Agent Tool Renderers
 * 将 SSE tool_result JSON 渲染为富 HTML 组件
 */
(function () {
  'use strict'

  // ─── Helpers ───
  function esc(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }

  // ─── 题目卡片列表 ───
  function renderQuestionCards(data) {
    var qs = data.questions || (Array.isArray(data) ? data : [])
    if (!qs.length) return '<p style="color:#74777f">暂无题目</p>'
    return qs.map(function(q, i) {
      var status = q.overall_status || 'passed'
      var auditLabel = {passed:'✓ 通过',warning:'⚠ 需确认',blocked:'✗ 拦截'}[status] || status
      var opts = ''
      if (q.options) {
        var arr = typeof q.options === 'string' ? q.options.split(',') : q.options
        opts = '<div style="font-size:12px;color:#3d3d56;margin-top:4px;font-family:JetBrains Mono">' + arr.map(function(o){return esc(o.trim())}).join(' &nbsp; ') + '</div>'
      }
      var tags = (q.knowledge_points || []).map(function(k){return '<span class="tag tag-medium">'+esc(k)+'</span>'}).join('')
      var diffTag = q.difficulty ? '<span class="tag tag-'+q.difficulty+'">'+q.difficulty+'</span>' : ''
      return '<div class="card card-accent qcard-enter" style="animation-delay:'+(i*.05).toFixed(2)+'s;margin-bottom:6px">'+
        '<span class="audit-badge '+status+'">'+auditLabel+'</span>'+
        '<p style="font-weight:600;font-size:13px">#'+(i+1)+' '+esc(q.content)+'</p>'+opts+
        '<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">'+
        '<span class="tag" style="background:#e0f2f1;color:#004f50">答案: '+esc(q.answer||'')+'</span>'+diffTag+'</div>'+
        (q.analysis?'<p style="font-size:12px;color:#3d3d56;margin-top:4px">'+esc(q.analysis)+'</p>':'')+
        '<div style="margin-top:4px">'+tags+'</div></div>'
    }).join('')
  }

  // ─── 障碍诊断柱状图 + 学生列表 ───
  function renderBarrierOverview(data) {
    var dist = data.class_barrier_distribution || {}
    var concept = dist.concept || 0, reading = dist.reading || 0, expression = dist.expression || 0
    var maxVal = Math.max(concept, reading, expression, 1)
    var students = data.students || []
    var avgMastery = data.avg_mastery || 0
    var bars = [
      {label:'概念理解',val:concept,color:'#290068'},
      {label:'审题障碍',val:reading,color:'#002045'},
      {label:'表述障碍',val:expression,color:'#13696a'}
    ]
    var html = '<div style="display:flex;align-items:end;gap:20px;height:140px;padding:8px 0">'
    bars.forEach(function(b){
      var h = Math.max(Math.round(b.val/maxVal*100), 4)
      html += '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px">'+
        '<span style="font-weight:700;font-size:16px;font-family:Manrope;color:'+b.color+'">'+b.val+'</span>'+
        '<div style="flex:1;width:100%;max-width:60px;background:#e4e2de;border-radius:6px 6px 0 0;position:relative;overflow:hidden">'+
        '<div style="position:absolute;bottom:0;width:100%;height:'+h+'%;background:'+b.color+';border-radius:6px 6px 0 0;transition:height .5s cubic-bezier(.34,1.56,.64,1)"></div></div>'+
        '<span style="font-size:11px;color:#3d3d56;font-family:JetBrains Mono">'+b.label+'</span></div>'
    })
    html += '</div>'
    html += '<div style="display:flex;gap:10px;margin-top:12px">'+
      '<div class="card" style="flex:1;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope">'+(avgMastery*100).toFixed(0)+'%</span><p style="font-size:11px;color:#74777f">掌握度</p></div>'+
      '<div class="card" style="flex:1;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope">'+students.length+'</span><p style="font-size:11px;color:#74777f">诊断学生</p></div></div>'

    // Top 5 students
    if (students.length) {
      var sorted = students.slice().sort(function(a,b){return (b.barrier_type&&b.barrier_type[b.dominant_barrier]||0)-(a.barrier_type&&a.barrier_type[a.dominant_barrier]||0)})
      html += '<div style="margin-top:12px"><span style="font-size:12px;font-weight:600;font-family:Manrope">需关注学生</span>'
      sorted.slice(0, 5).forEach(function(s){
        var dom = s.dominant_barrier || ''
        var names = {concept:'概念',reading:'审题',expression:'表述'}
        html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;margin-top:4px;border:1px solid rgba(0,0,0,.06);border-radius:6px;font-size:13px">'+
          '<span style="font-weight:500">'+esc(s.student_name)+'</span>'+
          '<span class="tag tag-'+dom+'">'+((names[dom]||dom)+' '+Math.round((s.barrier_type&&s.barrier_type[dom]||0)*100)+'%')+'</span>'+
          '<span style="font-size:11px;color:#74777f">'+(s.weak_knowledge_points||[]).length+' 弱知识点</span></div>'
      })
      html += '</div>'
    }
    return html
  }

  // ─── 学习计划 ───
  function renderLearningPlan(data) {
    var plan = data.plan || data || {}
    var title = plan.plan_title || '个性化学习计划'
    var period = plan.plan_period || ''
    var tasks = plan.daily_tasks || []
    var weeks = plan.weekly_goals || []
    var barriers = plan.barrier_interventions || []
    var motivation = plan.motivation_tips || []
    var html = '<div style="border-left:4px solid #290068;padding:8px 14px;background:rgba(0,0,0,.01);border-radius:4px;margin-bottom:8px">'+
      '<div style="display:flex;justify-content:space-between;align-items:center"><span style="font-weight:700;font-family:Manrope;font-size:15px">'+esc(title)+'</span>'+
      (period?'<span style="font-size:11px;color:#74777f">周期: '+esc(period)+'</span>':'')+'</div>'

    if (barriers.length) {
      html += '<div style="margin-top:8px"><span style="font-size:12px;font-weight:600">干预策略</span>'
      barriers.forEach(function(b){
        html += '<div style="display:flex;gap:8px;padding:6px 10px;margin-top:3px;background:rgba(0,0,0,.02);border-radius:4px;font-size:12px"><span style="font-family:JetBrains Mono;font-size:10px;color:var(--methyl-green,#13696a);min-width:70px">'+esc(b.barrier||'')+'</span><div><span>'+esc(b.strategy||'')+'</span><p style="color:#74777f;font-size:11px">'+esc(b.practice_tips||'')+'</p></div></div>'
      })
      html += '</div>'
    }
    if (tasks.length) {
      html += '<div style="margin-top:8px"><span style="font-size:12px;font-weight:600">每日任务</span>'
      tasks.forEach(function(t){
        html += '<div style="display:flex;gap:8px;padding:6px 10px;margin-top:3px;background:rgba(0,0,0,.02);border-radius:4px;font-size:12px"><span style="font-family:JetBrains Mono;font-size:10px;color:var(--methyl-green,#13696a);min-width:70px">'+esc(t.day||'')+'</span><span>'+esc(t.content||'')+'</span></div>'
      })
      html += '</div>'
    }
    if (weeks.length) {
      html += '<div style="margin-top:8px"><span style="font-size:12px;font-weight:600">每周目标</span>'
      weeks.forEach(function(w){
        html += '<div style="display:flex;gap:8px;padding:6px 10px;margin-top:3px;background:rgba(0,0,0,.02);border-radius:4px;font-size:12px"><span style="font-family:JetBrains Mono;font-size:10px;color:var(--methyl-green,#13696a);min-width:70px">'+esc(w.week||'')+'</span><span>'+esc(w.milestone||'')+'</span></div>'
      })
      html += '</div>'
    }
    if (motivation.length) html += '<div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">'+motivation.map(function(m){return '<span class="tag" style="background:#e0f2f1;color:#004f50">'+esc(m)+'</span>'}).join('')+'</div>'
    html += '</div>'
    return html
  }

  // ─── 考试结果统计 ───
  function renderExamStats(data) {
    var students = data.students || []
    var html = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">'+
      '<div class="card" style="flex:1;min-width:80px;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope;color:#13696a">'+(data.total_students||0)+'</span><p style="font-size:11px;color:#74777f">学生总数</p></div>'+
      '<div class="card" style="flex:1;min-width:80px;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope">'+(data.completed_count||0)+'</span><p style="font-size:11px;color:#74777f">已完成</p></div>'+
      '<div class="card" style="flex:1;min-width:80px;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope;color:#2F855A">'+(data.total_questions||0)+'</span><p style="font-size:11px;color:#74777f">题目数</p></div>'+
      '<div class="card" style="flex:1;min-width:80px;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope;color:#C53030">'+((data.class_avg_accuracy||0)*100).toFixed(1)+'%</span><p style="font-size:11px;color:#74777f">均分</p></div></div>'
    if (students.length) {
      html += '<table class="data-table"><thead><tr><th>#</th><th>学生</th><th>答题</th><th>正确</th><th>正确率</th><th>得分</th></tr></thead><tbody>'
      students.forEach(function(s,i){
        var accColor = s.accuracy>=0.8?'#2F855A':s.accuracy>=0.6?'#002045':'#C53030'
        html += '<tr><td>'+(i+1)+'</td><td>'+esc(s.student_name)+'</td><td>'+s.answered+'/'+data.total_questions+'</td><td>'+s.correct+'</td><td style="color:'+accColor+';font-weight:600">'+(s.accuracy*100).toFixed(1)+'%</td><td>'+s.score.toFixed(1)+'</td></tr>'
      })
      html += '</tbody></table>'
    }
    return html
  }

  // ─── OCR 结果表 ───
  function renderOcrTable(data) {
    var results = data.results || (Array.isArray(data) ? data : [])
    if (!results.length) return '<p style="color:#74777f">无识别结果</p>'
    var qNums = [], seen = {}
    results.forEach(function(r){
      Object.keys(r.answers||{}).forEach(function(k){ if(!seen[k]){seen[k]=true;qNums.push(k)} })
    })
    qNums.sort()
    var html = '<table class="data-table" style="font-size:12px"><thead><tr><th>学号</th><th>姓名</th>'
    qNums.forEach(function(q){html+='<th>'+q+'</th>'})
    html += '</tr></thead><tbody>'
    results.forEach(function(r){
      html += '<tr><td style="font-family:JetBrains Mono;font-size:11px">'+esc(r.student_id)+'</td><td>'+esc(r.student_name||'')+'</td>'
      qNums.forEach(function(q){
        var a = (r.answers||{})[q]||{}
        var conf = a.confidence || 0
        var cCls = conf>=0.85?'color:#2F855A':conf>=0.6?'color:#e6a817':'color:#C53030'
        html += '<td><span>'+esc(a.answer||'--')+'</span><div style="font-size:10px;'+cCls+'">'+Math.round(conf*100)+'%</div></td>'
      })
      html += '</tr>'
    })
    html += '</tbody></table>'
    return html
  }

  // ─── JSON fallback ───
  function renderJson(data) {
    return '<pre style="font-size:11px;font-family:JetBrains Mono;white-space:pre-wrap;max-height:300px;overflow-y:auto;color:#3d3d56">' + esc(JSON.stringify(data, null, 2)) + '</pre>'
  }

  // ─── Renderer dispatch ───
  // ─── 搜索结果显示 ───
  function renderSearchResults(data) {
    var qs = data.questions || (Array.isArray(data) ? data : [])
    var total = data.total || qs.length
    if (!qs.length) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#74777f">题库中暂无匹配结果</div>'
    return '<div style="font-size:12px;color:#74777f;margin-bottom:6px">找到 ' + total + ' 道真题</div>' + qs.slice(0, 5).map(function(q, i) {
      return '<div class="card card-accent" style="padding:10px 14px;margin-bottom:4px;font-size:13px">' +
        '<span style="font-weight:600">' + (q.source||'') + ' · ' + (q.year||'') + '</span>' +
        '<p style="margin:4px 0">' + esc((q.content||'').substring(0, 150)) + '</p>' +
        '<span class="tag" style="background:#e0f2f1;color:#004f50;font-size:11px">答案: ' + esc(q.answer||'') + '</span>' +
        '</div>'
    }).join('') + (qs.length > 5 ? '<div style="font-size:12px;color:#74777f;text-align:center">...还有 '+(qs.length-5)+' 题</div>' : '')
  }

  // ─── 联网搜索结果摘要 ───
  function renderWebSearchResult(data) {
    var result = data.result || data.content || ''
    if (!result) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#74777f">搜索完成，未获取到相关内容</div>'
    if (data.error) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#C53030">搜索异常: ' + esc(data.error) + '</div>'
    return '<details class="card" style="padding:10px 14px;font-size:13px;cursor:pointer"><summary style="font-weight:500;color:#004f50">已获取搜索结果 (' + esc(data.query||'') + ')</summary><div style="margin-top:8px;max-height:200px;overflow-y:auto;white-space:pre-wrap;font-size:12px;color:#3d3d56">' + (result || '').substring(0, 2000) + '</div></details>'
  }

  window.ChemRenderers = {
    search_exam_bank: renderSearchResults,
    web_search: renderWebSearchResult,
    exam_generate: renderQuestionCards,
    exam_audit: renderQuestionCards,
    exam_search_historical: renderSearchResults,
    exam_results: renderExamStats,
    diagnosis_barrier: renderBarrierOverview,
    diagnosis_barrier_class: renderBarrierOverview,
    diagnosis_plan_generate: renderLearningPlan,
    diagnosis_plan: renderLearningPlan,
    parser_ocr: renderOcrTable,
    ocr_result: renderOcrTable,
  }

  window.ChemRender = function(toolName, data) {
    var fn = window.ChemRenderers[toolName]
    if (fn) return fn(data)
    return renderJson(data)
  }
})()
