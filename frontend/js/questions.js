// 题目管理
(function(){
  document.addEventListener('DOMContentLoaded',function(){loadQuestions()})
  window.searchQuestions=function(){loadQuestions(document.getElementById('q-keyword').value)}
  window.aiGenerate=function(){
    var kps=document.getElementById('q-kps').value,diff=document.getElementById('q-diff').value,qty=document.getElementById('q-qty').value
    fetch('/api/question/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({knowledge_points:kps.split(','),difficulty:diff,quantity:parseInt(qty)||5})})
      .then(r=>r.json()).then(d=>{showResult(d.questions||[],'AI 生成结果 ('+d.total+'题)');loadQuestions()})
      .catch(e=>alert('生成失败: '+e.message))
  }
  window.importPaper=function(){
    var file=document.getElementById('q-pdf').files[0];if(!file)return
    var fd=new FormData();fd.append('file',file)
    fetch('/api/question/import/ocr',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{alert('导入完成: '+JSON.stringify(d));loadQuestions()}).catch(e=>alert('导入失败: '+e.message))
  }
  function loadQuestions(kw){
    var url='/api/exam-bank/historical?limit=50'+(kw?'&keyword='+encodeURIComponent(kw):'')
    fetch(url).then(r=>r.json()).then(d=>{
      var list=d.questions||[],html=list.length?list.map(function(q){
        return '<div class="card card-accent"><div class="flex justify-between items-start"><div class="flex-1"><p class="font-bold text-sm" style="color:#002045">'+q.source+' · T'+q.question_number+'</p><p class="text-sm mt-1">'+q.content+'</p><div class="flex gap-2 mt-2">'+(q.knowledge_points||[]).map(function(k){return '<span class="tag tag-medium">'+k+'</span>'}).join('')+'</div></div><span class="tag tag-'+q.difficulty+'">'+q.difficulty+'</span></div></div>'
      }).join(''):'<div class="empty-state"><span class="material-symbols-outlined text-4xl" style="color:#c4c6cf">menu_book</span><p>暂无题目</p></div>'
      document.getElementById('q-list').innerHTML=html
    })
  }
  function showResult(questions,title){
    var html='<h3 class="text-lg font-bold mt-4 mb-2" style="font-family:Manrope">'+title+'</h3>'
    questions.forEach(function(q,i){html+='<div class="card card-accent mt-2"><span class="tag tag-medium" style="float:right">'+(q.difficulty||'medium')+'</span><p class="font-bold">第'+(i+1)+'题</p><p class="text-sm mt-1">'+q.content+'</p><div class="mt-2">'+(q.options||[]).map(function(o){return '<span class="text-sm mr-3" style="font-family:JetBrains Mono">'+o+'</span>'}).join('')+'</div><p class="text-sm mt-2" style="color:#2F855A">答案: '+q.answer+'</p></div>'})
    document.getElementById('q-list').insertAdjacentHTML('afterbegin',html)
  }
})()
