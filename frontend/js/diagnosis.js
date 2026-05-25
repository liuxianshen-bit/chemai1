// 障碍诊断
(function(){
  document.addEventListener('DOMContentLoaded',function(){
    fetch('/api/classes').then(function(r){return r.json()}).then(function(d){
      var sel=document.getElementById('diag-class'),list=d.classes||[]
      list.forEach(function(c){var o=document.createElement('option');o.value=c.class_id;o.textContent=c.name;sel.appendChild(o)})
    }).catch(function(e){console.error(e)})
    // 班级变化时加载考试列表
    document.getElementById('diag-class').addEventListener('change',function(){
      var cls=this.value;if(!cls)return
      fetch('/api/exam/list/'+cls).then(function(r){return r.json()}).then(function(d){
        var sel=document.getElementById('diag-exam'),list=Array.isArray(d)?d:(d.exams||[])
        sel.innerHTML='<option value="">选择考试...</option>'
        list.forEach(function(e){var o=document.createElement('option');o.value=e.record_id||e.id;o.textContent=e.name;sel.appendChild(o)})
      }).catch(function(){})
    })
  })
  window.runDiagnosis=function(){
    var cls=document.getElementById('diag-class').value,exam=document.getElementById('diag-exam').value
    if(!cls){alert('请选择班级');return}
    if(!exam){alert('请选择考试');return}
    fetch('/api/diagnosis/barrier/'+cls+'/'+exam).then(function(r){return r.json()}).then(function(d){
      var s=d.students||[],concept=s.filter(function(x){return x.dominant_barrier==='concept'}).length
      var reading=s.filter(function(x){return x.dominant_barrier==='reading'}).length
      var expression=s.filter(function(x){return x.dominant_barrier==='expression'}).length
      var total=s.length||1
      document.getElementById('diag-result').innerHTML=
        '<div class="grid grid-cols-3 gap-4 mb-6">'+
        '<div class="card text-center"><h3 class="text-2xl font-bold" style="color:#290068;font-family:Manrope">'+concept+'</h3><p class="text-sm" style="color:#43474e">概念理解型</p><div class="progress-bar mt-2"><div class="progress-fill" style="width:'+(concept/total*100)+'%"></div></div></div>'+
        '<div class="card text-center"><h3 class="text-2xl font-bold" style="color:#002045;font-family:Manrope">'+reading+'</h3><p class="text-sm" style="color:#43474e">审题障碍型</p><div class="progress-bar mt-2"><div class="progress-fill" style="width:'+(reading/total*100)+'%;background:linear-gradient(90deg,#002045,#455f88)"></div></div></div>'+
        '<div class="card text-center"><h3 class="text-2xl font-bold" style="color:#13696a;font-family:Manrope">'+expression+'</h3><p class="text-sm" style="color:#43474e">表述障碍型</p><div class="progress-bar mt-2"><div class="progress-fill" style="width:'+(expression/total*100)+'%;background:linear-gradient(90deg,#13696a,#a2eded)"></div></div></div>'+
        '</div><h3 class="text-lg font-bold mb-3" style="font-family:Manrope">需关注学生</h3>'+
        s.slice(0,10).map(function(st){return'<div class="card card-accent flex justify-between items-center"><div><span class="font-bold">'+st.student_name+'</span><span class="tag ml-2 tag-'+st.dominant_barrier+'">'+st.dominant_barrier+'</span></div><div class="flex gap-2 items-center"><span class="text-sm" style="color:#74777f">'+st.recommended_intervention+'</span><button class="btn-teal text-xs" onclick="genPlan(\''+st.student_id+'\')">生成学习计划</button></div></div>'}).join('')
    }).catch(function(e){alert('诊断失败: '+e.message)})
  }
  window.genPlan=function(sid){
    fetch('/api/diagnosis/learning-plan/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({student_id:sid,barrier_type:'concept',weak_knowledge_points:[]})})
      .then(function(r){return r.json()}).then(function(){alert('学习计划已生成!')}).catch(function(e){alert('生成失败: '+e.message)})
  }
})()
