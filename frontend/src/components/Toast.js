/**
 * Toast 通知组件 - 统一封装
 */

const ToastIcons = {
  success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>`,
  error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>`,
  warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
  info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>`
}

class ToastManager {
  constructor() {
    this.container = null
    this.init()
  }

  init() {
    if (this.container) return
    this.container = document.createElement('div')
    this.container.id = 'toast-container'
    this.container.className = 'toast-container'
    this.container.innerHTML = `
      <style>
        .toast-container {
          position: fixed;
          top: 20px;
          left: 50%;
          transform: translateX(-50%);
          z-index: 9999;
          display: flex;
          flex-direction: column;
          gap: 8px;
          pointer-events: none;
        }
        .toast {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 20px;
          background: var(--toast-bg, #1c1c1c);
          color: white;
          border-radius: 8px;
          font-size: 14px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          animation: toastIn 0.3s ease;
          pointer-events: auto;
          min-width: 200px;
          max-width: 400px;
        }
        .toast.toast-hide {
          animation: toastOut 0.3s ease forwards;
        }
        .toast-icon {
          width: 20px;
          height: 20px;
          flex-shrink: 0;
        }
        .toast-icon svg {
          width: 100%;
          height: 100%;
        }
        .toast-success { background: #2d8b57; }
        .toast-error { background: #c94043; }
        .toast-warning { background: #c4882f; }
        .toast-info { background: #4a7fa8; }
        @keyframes toastIn {
          from { opacity: 0; transform: translateY(-20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes toastOut {
          from { opacity: 1; transform: translateY(0); }
          to { opacity: 0; transform: translateY(-20px); }
        }
      </style>
    `
    document.body.appendChild(this.container)
  }

  show(type, message, duration = 3000) {
    if (!this.container) this.init()

    const toast = document.createElement('div')
    toast.className = `toast toast-${type}`
    toast.innerHTML = `
      <span class="toast-icon">${ToastIcons[type] || ToastIcons.info}</span>
      <span class="toast-message">${message}</span>
    `
    this.container.appendChild(toast)

    setTimeout(() => {
      toast.classList.add('toast-hide')
      setTimeout(() => toast.remove(), 300)
    }, duration)
  }

  success(message, duration) {
    this.show('success', message, duration)
  }

  error(message, duration) {
    this.show('error', message, duration)
  }

  warning(message, duration) {
    this.show('warning', message, duration)
  }

  info(message, duration) {
    this.show('info', message, duration)
  }
}

// 创建全局单例
const Toast = new ToastManager()

// 导出
export { Toast }

// 如果在全局环境，也挂载到window
if (typeof window !== 'undefined') {
  window.Toast = Toast
}
