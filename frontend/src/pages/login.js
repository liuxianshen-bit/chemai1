/**
 * 登录页 - Login Page
 */
import { authService } from '../services/index.js'
import { Toast } from '../components/index.js'

export function initLogin() {
  const form = document.getElementById('login-form')
  if (form) {
    form.addEventListener('submit', handleLogin)
  }
}

async function handleLogin(e) {
  e.preventDefault()

  const username = document.getElementById('username')?.value?.trim()
  const password = document.getElementById('password')?.value
  const role = document.getElementById('role')?.value

  if (!username || !password) {
    Toast.error('请输入用户名和密码')
    return
  }

  try {
    Toast.info('登录中...')
    const result = await authService.login(username, password, role)

    if (result.success && result.data) {
      // 保存token和用户信息到session
      const { user, token } = result.data
      authService.saveSession(user, token)

      Toast.success('登录成功')
      setTimeout(() => {
        window.location.href = '/index.html'
      }, 500)
    } else {
      Toast.error(result.message || '登录失败')
    }
  } catch (error) {
    Toast.error('登录失败：' + error.message)
  }
}

export default { initLogin }
