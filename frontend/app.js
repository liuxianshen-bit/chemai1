/**
 * ChemAI Frontend — 公共函数
 * login.html 依赖此文件中的 apiRequest 函数
 */
async function apiRequest(endpoint, options = {}) {
  var session = sessionStorage.getItem('chemai_user')
  var token = session ? JSON.parse(session).token : null
  var headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = 'Bearer ' + token

  try {
    var resp = await fetch(endpoint, {
      method: options.method || 'GET',
      headers: Object.assign(headers, options.headers || {}),
      body: options.body || undefined
    })
    if (resp.status === 401) {
      sessionStorage.removeItem('chemai_user')
      window.location.href = '/login.html'
      throw new Error('登录已过期')
    }
    if (!resp.ok) throw new Error('HTTP ' + resp.status)
    return await resp.json()
  } catch (e) {
    console.error('API请求失败 [' + endpoint + ']:', e.message)
    throw e
  }
}
window.apiRequest = apiRequest

function handleOcrClassSelect() {
  var dropdown = document.getElementById('ocr-class-dropdown')
  if (!dropdown) return
  if (dropdown.options.length <= 1 && !dropdown._loading) {
    dropdown._loading = true
    apiRequest('/api/classes')
      .then(function(data) {
        dropdown._loading = false
        var list = (data && data.classes) || (Array.isArray(data) ? data : [])
        dropdown.innerHTML = '<option value="">请选择班级...</option>'
        list.forEach(function(c) {
          var opt = document.createElement('option')
          opt.value = c.class_id || ''
          opt.textContent = c.name || '未知班级'
          dropdown.appendChild(opt)
        })
      })
      .catch(function(e) {
        dropdown._loading = false
        console.error('加载班级失败:', e)
      })
    return
  }
  if (!dropdown.value) {
    alert('请先选择班级，再上传答题卡')
    dropdown.focus()
    return
  }
  var fileInput = document.getElementById('file-input')
  if (fileInput) fileInput.click()
}
window.handleOcrClassSelect = handleOcrClassSelect
