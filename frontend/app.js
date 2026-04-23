/**
 * ChemAI Frontend - API兼容层
 * 为 login.html 提供 apiRequest 函数
 */
const API_BASE = 'http://localhost:8001'

async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const session = sessionStorage.getItem('chemai_user')
  const token = session ? JSON.parse(session).token : null

  const headers = {
    'Content-Type': 'application/json'
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      headers: { ...headers, ...(options.headers || {}) },
      body: options.body || undefined
    })

    if (response.status === 401) {
      sessionStorage.removeItem('chemai_user')
      window.location.href = '/login.html'
      throw new Error('登录已过期')
    }

    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return await response.json()
  } catch (error) {
    console.error(`API请求失败 [${endpoint}]:`, error.message)
    throw error
  }
}

window.apiRequest = apiRequest
