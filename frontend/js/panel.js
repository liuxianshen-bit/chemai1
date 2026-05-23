// 学情面板
(function(){
  document.addEventListener('DOMContentLoaded',function(){
    fetch('/api/classes').then(r=>r.json()).then(d=>{
      var sel=document.getElementById('panel-class'),list=d.classes||(Array.isArray(d)?d:[])
      list.forEach(function(c){var o=document.createElement('option');o.value=c.class_id;o.textContent=c.name;sel.appendChild(o)})
    })
  })
  window.loadPanel=function(){
    var cls=document.getElementById('panel-class').value
    if(!cls){alert('请选择班级');return}
    fetch('/api/panel/class/'+cls).then(r=>r.json()).then(d=>{
      var ov=d.class_overview||{},bd=d.barrier_distribution||{}
      document.getElementById('panel-content').innerHTML=
        '<div class="card mb-4"><h3 class="text-lg font-bold" style="font-family:Manrope">'+ov.class_name+'</h3><p class="text-sm" style="color:#43474e">共 '+ov.total_students+' 名学生 · 最近考试: '+(ov.recent_exam_date||'无')+' · 均分: '+(ov.recent_exam_avg||0)+'</p></div>'+
        '<div class="card"><h3 class="text-lg font-bold mb-3" style="font-family:Manrope">障碍类型分布</h3>'+
        '<div class="flex gap-4"><div class="flex-1 text-center"><p class="text-2xl font-bold" style="color:#290068;font-family:Manrope">'+(bd.concept||0)+'</p><p class="text-sm">概念理解</p></div><div class="flex-1 text-center"><p class="text-2xl font-bold" style="color:#002045;font-family:Manrope">'+(bd.reading||0)+'</p><p class="text-sm">审题障碍</p></div><div class="flex-1 text-center"><p class="text-2xl font-bold" style="color:#13696a;font-family:Manrope">'+(bd.expression||0)+'</p><p class="text-sm">表述障碍</p></div></div></div>'
    }).catch(function(e){alert('加载失败: '+e.message)})
  }
})()
