/**
 * 加载状态组件 - Loading / Skeleton
 */

/**
 * 显示全屏加载
 */
export function showLoading(text = '加载中...') {
  hideLoading()
  const overlay = document.createElement('div')
  overlay.id = 'loading-overlay'
  overlay.innerHTML = `
    <style>
      #loading-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.5);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 9998;
        gap: 16px;
      }
      .loading-spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255,255,255,0.3);
        border-top-color: white;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
      }
      .loading-text {
        color: white;
        font-size: 14px;
      }
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
    </style>
    <div class="loading-spinner"></div>
    <div class="loading-text">${text}</div>
  `
  document.body.appendChild(overlay)
  return overlay
}

/**
 * 隐藏全屏加载
 */
export function hideLoading() {
  const overlay = document.getElementById('loading-overlay')
  if (overlay) {
    overlay.remove()
  }
}

/**
 * 显示按钮加载状态
 */
export function setButtonLoading(button, loading = true) {
  if (loading) {
    button.dataset.originalText = button.textContent
    button.disabled = true
    button.innerHTML = `
      <span style="display: inline-flex; align-items: center; gap: 8px;">
        <span class="btn-spinner" style="width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite;"></span>
        处理中...
      </span>
    `
  } else {
    button.disabled = false
    button.textContent = button.dataset.originalText || '提交'
  }
}

/**
 * 骨架屏组件
 */
export function showSkeleton(container, count = 3) {
  container.innerHTML = Array(count).fill('').map(() => `
    <div class="skeleton-item" style="
      background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
      height: 60px;
      border-radius: 8px;
      margin-bottom: 12px;
    "></div>
  `).join('') + `
    <style>
      @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
    </style>
  `
}

/**
 * 空状态组件
 */
export function showEmpty(container, message = '暂无数据', actionText = '', onAction = null) {
  container.innerHTML = `
    <div style="
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px 20px;
      color: #909090;
      text-align: center;
    ">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.5;">
        <path d="M20 6L9 17l-5-5"/>
      </svg>
      <p style="margin-bottom: 16px;">${message}</p>
      ${actionText ? `<button class="btn-primary" style="padding: 8px 16px; font-size: 14px;">${actionText}</button>` : ''}
    </div>
  `

  if (actionText && onAction) {
    const btn = container.querySelector('button')
    if (btn) btn.addEventListener('click', onAction)
  }
}
