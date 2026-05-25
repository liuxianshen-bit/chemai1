// 学情报告
(function(){
  document.addEventListener('DOMContentLoaded',function(){
    fetch('/api/classes').then(function(r){return r.json()}).then(function(d){
      var sel=document.getElementById('report-class'),list=d.classes||[]
      list.forEach(function(c){var o=document.createElement('option');o.value=c.class_id;o.textContent=c.name;sel.appendChild(o)})
    })
    document.getElementById('report-class').addEventListener('change',function(){
      var cls=this.value;if(!cls)return
      fetch('/api/exam/list/'+cls).then(function(r){return r.json()}).then(function(d){
        var sel=document.getElementById('report-exam'),list=Array.isArray(d)?d:(d.exams||[])
        sel.innerHTML='<option value="">选择考试...</option>'
        list.forEach(function(e){var o=document.createElement('option');o.value=e.record_id||e.id;o.textContent=e.name;sel.appendChild(o)})
      }).catch(function(){})
    })
  })
  window.loadReport=function(){
    var cls=document.getElementById('report-class').value,exam=document.getElementById('report-exam').value
    if(!cls){alert('请选择班级');return}
    if(!exam){alert('请选择考试');return}
    fetch('/api/report/teacher/'+exam).then(function(r){return r.json()}).then(function(d){
      document.getElementById('report-content').innerHTML=
        '<div class="card"><h3 class="text-lg font-bold" style="font-family:Manrope">'+d.exam_name+'</h3>'+
        '<div class="grid grid-cols-3 gap-4 mt-4">'+
        '<div class="text-center"><p class="text-3xl font-bold" style="color:#002045;font-family:Manrope">'+d.total_students+'</p><p class="text-sm" style="color:#43474e">参考人数</p></div>'+
        '<div class="text-center"><p class="text-3xl font-bold" style="color:#13696a;font-family:Manrope">'+(d.avg_score||0)+'</p><p class="text-sm" style="color:#43474e">平均分</p></div>'+
        '<div class="text-center"><p class="text-3xl font-bold" style="color:#290068;font-family:Manrope">'+(d.present_students||0)+'</p><p class="text-sm" style="color:#43474e">实到人数</p></div>'+
        '</div></div>'+
        (d.questions&&d.questions.length?'<h3 class="text-lg font-bold mt-6 mb-3" style="font-family:Manrope">错题分布</h3>'+d.questions.map(function(q){return'<div class="card card-accent mt-2"><span class="text-sm font-bold" style="font-family:JetBrains Mono">T'+q.number+'</span><span class="text-sm ml-4" style="color:#43474e">错误率: '+(q.error_rate||0)+'%</span></div>'}).join(''):'<div class="empty-state mt-6"><p>暂无题目数据</p></div>')
    }).catch(function(e){alert('加载失败: '+e.message)})
  }
})()
