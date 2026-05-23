/**
 * API 服务层 - 统一封装所有API调用
 * 包含错误处理、请求拦截、响应拦截
 */

const API_BASE = ''  // 通过 Vite proxy 转发到 FastAPI

// ============================================
// API 错误类
// ============================================
export class ApiError extends Error {
  constructor(message, status, code) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

// ============================================
// 请求拦截器
// ============================================
const requestInterceptors = []

// ============================================
// 响应拦截器
// ============================================
const responseInterceptors = []

/**
 * 添加请求拦截器
 */
export function addRequestInterceptor(interceptor) {
  requestInterceptors.push(interceptor)
}

/**
 * 添加响应拦截器
 */
export function addResponseInterceptor(interceptor) {
  responseInterceptors.push(interceptor)
}

// ============================================
// 获取token
// ============================================
function getAuthToken() {
  const session = sessionStorage.getItem('chemai_user')
  if (session) {
    try {
      const user = JSON.parse(session)
      return user.token || null
    } catch {
      return null
    }
  }
  return null
}

// ============================================
// 刷新token
// ============================================
async function tryRefreshToken() {
  const session = sessionStorage.getItem('chemai_user')
  if (!session) return false
  try {
    const user = JSON.parse(session)
    if (!user.refreshToken) return false
    const response = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: user.refreshToken })
    })
    if (response.ok) {
      const data = await response.json()
      if (data.success && data.token) {
        user.token = data.token
        sessionStorage.setItem('chemai_user', JSON.stringify(user))
        return true
      }
    }
  } catch (e) {
    console.warn('刷新token失败:', e)
  }
  return false
}

// ============================================
// 核心请求方法
// ============================================
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`

  // 获取token并添加到header
  const token = getAuthToken()
  const headers = {
    'Content-Type': 'application/json'
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const defaultOptions = {
    headers,
    credentials: 'include'
  }

  // 执行请求拦截器
  let modifiedOptions = { ...defaultOptions, ...options }
  if (modifiedOptions.headers) {
    modifiedOptions.headers = { ...headers, ...modifiedOptions.headers }
  }
  for (const interceptor of requestInterceptors) {
    modifiedOptions = await interceptor(modifiedOptions)
  }

  try {
    const response = await fetch(url, modifiedOptions)

    // 401 Unauthorized - 尝试刷新token
    if (response.status === 401) {
      const refreshed = await tryRefreshToken()
      if (refreshed) {
        // 重试请求
        const newToken = getAuthToken()
        modifiedOptions.headers['Authorization'] = `Bearer ${newToken}`
        const retryResponse = await fetch(url, modifiedOptions)
        const contentType = retryResponse.headers.get('content-type')
        let data
        if (contentType && contentType.includes('application/json')) {
          data = await retryResponse.json()
        } else {
          data = await retryResponse.text()
        }
        if (!retryResponse.ok) {
          throw new ApiError(
            data.message || `HTTP ${retryResponse.status}: ${retryResponse.statusText}`,
            retryResponse.status,
            data.code
          )
        }
        return data
      }
      // 刷新失败，清除会话并跳转登录
      sessionStorage.removeItem('chemai_user')
      window.location.href = '/login.html'
      throw new ApiError('登录已过期', 401, 'UNAUTHORIZED')
    }

    // 执行响应拦截器
    let data
    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      data = await response.json()
    } else {
      data = await response.text()
    }

    // 检查HTTP状态
    if (!response.ok) {
      throw new ApiError(
        data.message || `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        data.code
      )
    }

    return data
  } catch (error) {
    // 如果是ApiError直接抛出
    if (error instanceof ApiError) {
      throw error
    }

    // 网络错误
    if (error.name === 'TypeError' && error.message === 'Failed to fetch') {
      throw new ApiError('网络连接失败，请检查网络', 0, 'NETWORK_ERROR')
    }

    throw new ApiError(error.message || '未知错误', 0, 'UNKNOWN_ERROR')
  }
}

// ============================================
// 封装常用HTTP方法
// ============================================
export const api = {
  get(endpoint, params = {}) {
    const query = new URLSearchParams(params).toString()
    const url = query ? `${endpoint}?${query}` : endpoint
    return request(url, { method: 'GET' })
  },

  post(endpoint, data) {
    return request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  put(endpoint, data) {
    return request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data)
    })
  },

  delete(endpoint) {
    return request(endpoint, { method: 'DELETE' })
  }
}

// ============================================
// 默认错误处理
// ============================================
export function handleApiError(error, toast = true) {
  console.error('API Error:', error)

  if (toast && typeof Toast !== 'undefined') {
    if (error.code === 'NETWORK_ERROR') {
      Toast.error('网络连接失败')
    } else if (error.code === 'UNAUTHORIZED') {
      Toast.error('登录已过期，请重新登录')
      setTimeout(() => {
        window.location.href = 'login.html'
      }, 1500)
    } else {
      Toast.error(error.message || '请求失败')
    }
  }

  return error
}

// ============================================
// 导出API服务
// ============================================
export * from './auth.js'
export * from './exam.js'
export * from './question.js'
export * from './diagnosis.js'
export * from './practice.js'
export * from './report.js'
export * from './user.js'
export * from './school.js'
