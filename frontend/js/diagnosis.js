// 障碍诊断
(function(){
  document.addEventListener('DOMContentLoaded',function(){
    fetch('/api/classes').then(r=>r.json()).then(d=>{
      var sel=document.getElementById('diag-class'),list=d.classes||(Array.isArray(d)?d:[])
      list.forEach(function(c){var o=document.createElement('option');o.value=c.class_id;o.textContent=c.name;sel.appendChild(o)})
    }).catch(e=>console.error(e))
  })
  window.runDiagnosis=function(){
    var cls=document.getElementById('diag-class').value
    if(!cls){alert('请选择班级');return}
    fetch('/api/diagnosis/barrier/'+cls+'/demo_exam_001').then(r=>r.json()).then(d=>{
      var s=d.students||[],concept=s.filter(function(x){return x.dominant_barrier==='concept'}).length
      var reading=s.filter(function(x){return x.dominant_barrier==='reading'}).length
      var expression=s.filter(function(x){return x.dominant_barrier==='expression'}).length
      document.getElementById('diag-result').innerHTML=
        '<div class="grid grid-cols-3 gap-4 mb-6">'+
        '<div class="card text-center"><h3 class="text-2xl font-bold" style="color:#290068;font-family:Manrope">'+concept+'</h3><p class="text-sm" style="color:#43474e">概念理解型</p><div class="progress-bar mt-2"><div class="progress-fill" style="width:'+(concept/s.length*100)+'%"></div></div></div>'+
        '<div class="card text-center"><h3 class="text-2xl font-bold" style="color:#002045;font-family:Manrope">'+reading+'</h3><p class="text-sm" style="color:#43474e">审题障碍型</p><div class="progress-bar mt-2"><div class="progress-fill" style="width:'+(reading/s.length*100)+'%;background:linear-gradient(90deg,#002045,#455f88)"></div></div></div>'+
        '<div class="card text-center"><h3 class="text-2xl font-bold" style="color:#13696a;font-family:Manrope">'+expression+'</h3><p class="text-sm" style="color:#43474e">表述障碍型</p><div class="progress-bar mt-2"><div class="progress-fill" style="width:'+(expression/s.length*100)+'%;background:linear-gradient(90deg,#13696a,#a2eded)"></div></div></div>'+
        '</div><h3 class="text-lg font-bold mb-3" style="font-family:Manrope">需关注学生</h3>'+
        s.slice(0,10).map(function(st){return '<div class="card card-accent flex justify-between items-center"><div><span class="font-bold">'+st.student_name+'</span><span class="tag ml-2 tag-'+st.dominant_barrier+'">'+st.dominant_barrier+'</span></div><span class="text-sm" style="color:#74777f">建议: '+st.recommended_intervention+'</span></div>'}).join('')
    }).catch(function(e){alert('诊断失败: '+e.message)})
  }
})()
