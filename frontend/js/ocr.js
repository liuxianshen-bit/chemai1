// OCR 答题卡识别
(function(){
  document.addEventListener('DOMContentLoaded',function(){
    fetch('/api/classes').then(r=>r.json()).then(d=>{
      var sel=document.getElementById('ocr-class'),list=d.classes||(Array.isArray(d)?d:[])
      list.forEach(c=>{var o=document.createElement('option');o.value=c.class_id;o.textContent=c.name;sel.appendChild(o)})
    }).catch(e=>console.error('加载班级失败',e))
  })
  window.handleUpload=function(){
    var cls=document.getElementById('ocr-class')
    if(!cls.value){alert('请先选择班级');cls.focus();return}
    document.getElementById('file-input').click()
  }
  window.handleFiles=function(files){
    if(!files||!files.length)return
    var container=document.getElementById('ocr-results')
    container.innerHTML='<div class="card mt-4"><p>正在识别 '+files.length+' 个文件...</p><div class="progress-bar mt-3"><div class="progress-fill pulse" style="width:60%"></div></div></div>'
    Array.from(files).forEach(function(f){
      var fd=new FormData();fd.append('file',f)
      fetch('/api/ocr/recognize',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{
        var cls=d.success?'formula-green':'academic-red'
        container.innerHTML+='<div class="card card-accent mt-3"><div class="flex justify-between items-center"><span style="font-family:JetBrains Mono;font-size:13px">'+f.name+'</span><span style="color:var(--color-'+cls+')">'+(d.success?'识别完成':'识别失败')+'</span></div><pre style="font-family:JetBrains Mono;font-size:11px;margin-top:8px;color:#43474e">'+JSON.stringify(d,null,2)+'</pre></div>'
      }).catch(function(e){
        container.innerHTML+='<div class="card mt-3" style="border-left:3px solid #C53030">❌ '+f.name+': '+e.message+'</div>'
      })
    })
  }
})()
