// 考试管理
(function(){
  document.addEventListener('DOMContentLoaded',function(){loadClasses();loadExams()})
  function loadClasses(){
    fetch('/api/classes').then(function(r){return r.json()}).then(function(d){
      var sel=document.getElementById('exam-class'),list=d.classes||[]
      list.forEach(function(c){var o=document.createElement('option');o.value=c.class_id;o.textContent=c.name;sel.appendChild(o)})
    })
  }
  window.loadExams=function(){
    fetch('/api/classes').then(function(r){return r.json()}).then(function(d){
      var list=d.classes||(Array.isArray(d)?d:[]),exams=[]
      Promise.all(list.map(function(c){return fetch('/api/exam/list/'+c.class_id).then(function(r){return r.json()}).catch(function(){return[]})})).then(function(results){
        results.forEach(function(r,i){if(r&&r.length)r.forEach(function(e){e.class_name=list[i].name;exams.push(e)})})
        document.getElementById('exam-list').innerHTML=exams.length?exams.map(function(e){return'<div class="card card-accent"><div class="flex justify-between items-center"><div><span class="font-bold">'+e.name+'</span><span class="text-sm ml-4" style="color:#43474e">'+e.class_name+'</span></div></div><div class="flex gap-4 mt-2 text-sm" style="color:#43474e"><span>'+e.total_students+'人参试</span><span>均分: '+(e.avg_score||0)+'</span></div></div>'}).join(''):'<div class="empty-state"><span class="material-symbols-outlined text-4xl" style="color:#c4c6cf">assignment</span><p>暂无考试</p></div>'
      })
    })
  }
  window.createExam=function(){
    var name=document.getElementById('exam-name').value,cls=document.getElementById('exam-class').value
    if(!name){alert('请输入考试名称');return}
    if(!cls){alert('请选择班级');return}
    fetch('/api/exam/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,class_id:cls,total_students:34})})
      .then(function(r){return r.json()}).then(function(d){alert('创建成功!');loadExams()}).catch(function(e){alert('创建失败: '+e.message)})
  }
})()
