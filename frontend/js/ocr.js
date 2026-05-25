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
    var results=[]
    Array.from(files).forEach(function(f){
      var fd=new FormData();fd.append('file',f)
      fetch('/api/ocr/recognize',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
        results.push({name:f.name,data:d})
        if(results.length===files.length)renderOcrResults(results,container)
      }).catch(function(e){
        results.push({name:f.name,data:{success:false,error:e.message}})
        if(results.length===files.length)renderOcrResults(results,container)
      })
    })
  }
  function renderOcrResults(results,container){
    var html='<h3 class="text-lg font-bold mt-4 mb-2" style="font-family:Manrope">识别结果</h3>'
    results.forEach(function(r){
      var d=r.data,ok=d.success,answers=d.answers||{}
      var aHtml=Object.keys(answers).map(function(k){return'<span class="text-sm mr-2" style="font-family:JetBrains Mono">'+k+': '+answers[k]+'</span>'}).join('')
      html+='<div class="card card-accent mt-2"><div class="flex justify-between items-center"><span style="font-family:JetBrains Mono;font-size:13px">'+r.name+'</span><span style="color:'+(ok?'#2F855A':'#C53030')+'">'+(ok?'✅ 识别完成':'❌ '+(d.error||'失败'))+'</span></div>'+
        '<p class="text-sm mt-1" style="color:#43474e">学号: '+(d.student_id||'未知')+' | 姓名: '+(d.student_name||'未知')+'</p><div class="mt-1">'+aHtml+'</div>'+
        (ok?'<button class="btn-teal text-sm mt-2" onclick="confirmOcr(\''+d.student_id+'\')">确认入库</button>':'')+
        '</div>'
    })
    container.innerHTML=html
  }
  window.confirmOcr=function(sid){
    fetch('/api/ocr/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({student_id:sid,class_id:document.getElementById('ocr-class').value})})
      .then(function(r){return r.json()}).then(function(){alert('入库成功!')}).catch(function(e){alert('入库失败: '+e.message)})
  }
})()
