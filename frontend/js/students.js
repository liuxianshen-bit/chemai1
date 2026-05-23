// 学生管理
(function(){
  document.addEventListener('DOMContentLoaded',function(){loadStudents()})
  window.loadStudents=function(kw){
    fetch('/api/users/students').then(r=>r.json()).then(d=>{
      var list=d.students||(Array.isArray(d)?d:[])
      if(kw)list=list.filter(function(s){return s.name.indexOf(kw)>=0||s.student_id.indexOf(kw)>=0})
      document.getElementById('students-list').innerHTML=list.length?list.map(function(s){
        var b=s.barrier_type||{},dominant=Object.keys(b).sort(function(a,b){return b[a]-a[b]})[0]||''
        return'<div class="card card-accent flex justify-between items-center"><div><span class="font-bold">'+s.name+'</span><span class="text-sm ml-2" style="color:#43474e;font-family:JetBrains Mono">'+s.student_id+'</span></div><div class="flex gap-2 items-center"><span class="tag tag-'+dominant+'">'+dominant+'</span><span class="text-sm" style="color:#74777f">练习:'+(s.exercises_completed||0)+'次</span></div></div>'
      }).join(''):'<div class="empty-state"><span class="material-symbols-outlined text-4xl" style="color:#c4c6cf">group</span><p>暂无学生</p></div>'
    }).catch(function(e){console.error(e)})
  }
})()
