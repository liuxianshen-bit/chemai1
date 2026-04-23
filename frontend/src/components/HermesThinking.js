/**
 * Hermes Agent 流式思考展示组件
 * 用于展示 Agent 的 ReAct 工作过程
 */

import { HermesEventType, TaskType } from '../services/hermes.js'

// 工具图标
const ToolIcons = {
  exam_ocr_recognize: '📷',
  exam_generate: '📝',
  exam_import_questions: '📥',
  exam_search_historical: '🔍',
  diagnosis_barrier_class: '🔬',
  diagnosis_plan_generate: '📋',
  chemistry_parser: '📄',
  chemistry_memory: '🧠',
  chemistry_notification: '🔔',
  chemistry_improvement: '📈'
}

// 工具名称
const ToolNames = {
  exam_ocr_recognize: 'OCR识别',
  exam_generate: 'AI出题',
  exam_import_questions: '导入真题',
  exam_search_historical: '真题检索',
  diagnosis_barrier_class: '障碍诊断',
  diagnosis_plan_generate: '学习计划生成',
  chemistry_parser: '文档解析',
  chemistry_memory: '记忆检索'
}

class HermesThinkingManager {
  constructor() {
    this.container = null
    this.logs = []
    this.isActive = false
    this.currentTask = null
    this.onCancel = null
    this.onConfirm = null
    this.pendingConfirm = null
  }

  /**
   * 显示 Agent 思考中
   */
  show(options = {}) {
    const {
      task = 'default',
      message = 'AI正在思考中...',
      showLog = true,
      onCancel = null,
      onConfirm = null
    } = options

    this.currentTask = task
    this.isActive = true
    this.onCancel = onCancel
    this.onConfirm = onConfirm
    this.logs = []

    // 移除已存在的
    this.hide()

    // 创建容器
    this.container = document.createElement('div')
    this.container.id = 'hermes-thinking'
    this.container.innerHTML = this._renderTemplate()
    document.body.appendChild(this.container)

    // 绑定取消按钮
    const cancelBtn = this.container.querySelector('.hermes-cancel-btn')
    if (cancelBtn) {
      cancelBtn.onclick = () => this._handleCancel()
    }

    // 添加欢迎日志
    this.addLog('start', '🤖', 'Agent', '任务启动')

    return this
  }

  /**
   * 更新状态
   */
  update(event) {
    if (!this.container || !this.isActive) return this

    const { type, content, tool, params, result, confirmType, data } = event

    switch (type) {
      case HermesEventType.THINKING:
        this.updateThinking(content)
        break

      case HermesEventType.TOOL_CALL:
        this.addLog('tool', ToolIcons[tool] || '⚡', ToolNames[tool] || tool, '开始执行')
        this.updateStatus(`执行 ${ToolNames[tool] || tool}...`)
        break

      case HermesEventType.TOOL_RESULT:
        this.addLog('result', '📋', '工具', this._truncate(result, 50))
        break

      case HermesEventType.NEEDS_CONFIRMATION:
        this.showConfirmModal(confirmType, data)
        break

      case HermesEventType.CONFIRMED:
        this.hideConfirmModal()
        this.addLog('confirm', '✓', '已确认', '用户已确认，继续执行')
        break

      case HermesEventType.ERROR:
        this.addLog('error', '❌', '错误', content || '发生错误')
        break

      case HermesEventType.FINAL:
        this.addLog('complete', '✓', '完成', '任务已完成')
        this.updateStatus('处理完成')
        break
    }

    return this
  }

  /**
   * 更新思考内容
   */
  updateThinking(content) {
    if (!this.container) return

    const thinkingEl = this.container.querySelector('.hermes-thinking-content')
    if (thinkingEl) {
      thinkingEl.textContent = content || '思考中...'
    }

    // 添加日志
    if (content) {
      this.addLog('thinking', '🤔', '思考', content)
    }
  }

  /**
   * 更新状态消息
   */
  updateStatus(message) {
    if (!this.container) return

    const statusEl = this.container.querySelector('.hermes-status')
    if (statusEl) {
      statusEl.textContent = message
    }
  }

  /**
   * 添加日志
   */
  addLog(type, icon, agent, message) {
    this.logs.push({ type, icon, agent, message, time: Date.now() })

    if (!this.container) return

    const logList = this.container.querySelector('.hermes-log-list')
    if (logList) {
      const logEl = document.createElement('div')
      logEl.className = `hermes-log-item log-${type}`
      logEl.innerHTML = `
        <span class="log-icon">${icon}</span>
        <span class="log-agent">${agent}</span>
        <span class="log-message">${message}</span>
      `
      logList.appendChild(logEl)
      logList.scrollTop = logList.scrollHeight
    }
  }

  /**
   * 显示确认弹窗
   */
  showConfirmModal(confirmType, data) {
    if (!this.container) return

    this.pendingConfirm = { confirmType, data }

    const modal = this.container.querySelector('.hermes-confirm-modal')
    if (modal) {
      modal.style.display = 'block'
      const content = modal.querySelector('.hermes-confirm-content')
      if (content) {
        content.innerHTML = this._renderConfirmContent(confirmType, data)
      }
    }

    // 隐藏取消按钮，显示确认按钮
    const cancelBtn = this.container.querySelector('.hermes-cancel-btn')
    const confirmBtns = this.container.querySelector('.hermes-confirm-btns')
    if (cancelBtn) cancelBtn.style.display = 'none'
    if (confirmBtns) confirmBtns.style.display = 'flex'
  }

  /**
   * 隐藏确认弹窗
   */
  hideConfirmModal() {
    if (!this.container) return

    const modal = this.container.querySelector('.hermes-confirm-modal')
    if (modal) {
      modal.style.display = 'none'
    }

    // 显示取消按钮，隐藏确认按钮
    const cancelBtn = this.container.querySelector('.hermes-cancel-btn')
    const confirmBtns = this.container.querySelector('.hermes-confirm-btns')
    if (cancelBtn) cancelBtn.style.display = 'inline-block'
    if (confirmBtns) confirmBtns.style.display = 'none'
  }

  /**
   * 处理确认
   */
  async _handleConfirm(corrections = {}) {
    this.hideConfirmModal()
    if (this.onConfirm) {
      await this.onConfirm(corrections)
    }
  }

  /**
   * 处理取消
   */
  _handleCancel() {
    this.hide()
    if (this.onCancel) {
      this.onCancel()
    }
  }

  /**
   * 完成
   */
  complete(result = {}) {
    this.isActive = false

    setTimeout(() => {
      this.hide()
    }, 1000)

    return this
  }

  /**
   * 错误
   */
  error(message) {
    this.addLog('error', '❌', '错误', message)
    this.isActive = false

    setTimeout(() => {
      this.hide()
    }, 2000)

    return this
  }

  /**
   * 隐藏
   */
  hide() {
    if (this.container) {
      this.container.remove()
      this.container = null
    }
    this.isActive = false
    this.logs = []
    this.currentTask = null
    this.pendingConfirm = null
  }

  /**
   * 截断文本
   */
  _truncate(text, maxLength) {
    if (typeof text !== 'string') {
      text = JSON.stringify(text)
    }
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
  }

  /**
   * 渲染确认内容
   */
  _renderConfirmContent(confirmType, data) {
    switch (confirmType) {
      case 'ocr_preview':
        return this._renderOcrConfirm(data)
      case 'question_audit':
        return this._renderQuestionConfirm(data)
      case 'learning_plan':
        return this._renderPlanConfirm(data)
      default:
        return `<p>需要确认: ${JSON.stringify(data)}</p>
                <div class="confirm-actions">
                  <button class="btn-primary" onclick="HermesThinking.confirm({})">确认</button>
                </div>`
    }
  }

  /**
   * 渲染 OCR 确认
   */
  _renderOcrConfirm(data) {
    const answers = data?.answers || {}
    const lowConfidence = data?.low_confidence_answers || []

    let html = '<div class="confirm-section">'
    html += '<h4>OCR 识别结果</h4>'

    for (const [q, a] of Object.entries(answers)) {
      const isLow = lowConfidence.includes(q)
      html += `
        <div class="confirm-item ${isLow ? 'low-confidence' : ''}">
          <span class="q-num">第${q}题</span>
          <span class="q-answer">${a}</span>
          ${isLow ? '<span class="warning">⚠️ 低置信度</span>' : ''}
          <input type="text" data-question="${q}" value="${a}" class="correction-input">
        </div>
      `
    }

    html += '</div>'
    html += `
      <div class="confirm-actions">
        <button class="btn-secondary" onclick="HermesThinking.confirm({})">确认无误</button>
        <button class="btn-primary" onclick="HermesThinking.confirmWithCorrection()">确认并修正</button>
      </div>
    `
    return html
  }

  /**
   * 渲染题目确认
   */
  _renderQuestionConfirm(data) {
    const questions = data?.questions || []
    const warnings = data?.warnings || []

    let html = '<div class="confirm-section">'
    html += '<h4>生成的题目</h4>'

    for (const q of questions) {
      html += `
        <div class="confirm-item">
          <div class="q-content">${q.content || q.title}</div>
          <div class="q-meta">
            <span>答案: ${q.correct_answer}</span>
            <span>知识点: ${(q.knowledge_points || []).join(', ')}</span>
          </div>
        </div>
      `
    }

    if (warnings.length > 0) {
      html += '<div class="confirm-warnings">'
      html += '<h4>⚠️ 审核警告</h4>'
      for (const w of warnings) {
        html += `<p>${w}</p>`
      }
      html += '</div>'
    }

    html += '</div>'
    html += `
      <div class="confirm-actions">
        <button class="btn-secondary" onclick="HermesThinking.confirm({approved: false})">重新生成</button>
        <button class="btn-primary" onclick="HermesThinking.confirm({approved: true})">审核通过</button>
      </div>
    `
    return html
  }

  /**
   * 渲染学习计划确认
   */
  _renderPlanConfirm(data) {
    const plan = data?.plan || data

    let html = '<div class="confirm-section">'
    html += `<h4>${plan?.plan_title || '学习计划'}</h4>`
    html += `<p class="plan-period">周期: ${plan?.plan_period || '未知'}</p>`

    if (plan?.daily_tasks?.length > 0) {
      html += '<h5>每日任务</h5><ul>'
      for (const task of plan.daily_tasks.slice(0, 5)) {
        html += `<li>${task.day}: ${task.content}</li>`
      }
      if (plan.daily_tasks.length > 5) {
        html += `<li>...还有${plan.daily_tasks.length - 5}个任务</li>`
      }
      html += '</ul>'
    }

    html += '</div>'
    html += `
      <div class="confirm-actions">
        <button class="btn-secondary" onclick="HermesThinking.confirm({})">稍后再说</button>
        <button class="btn-primary" onclick="HermesThinking.confirm({apply: true})">应用到此学生</button>
      </div>
    `
    return html
  }

  /**
   * 确认（带修正）
   */
  confirmWithCorrection() {
    if (!this.container) return

    const inputs = this.container.querySelectorAll('.correction-input')
    const corrections = {}

    inputs.forEach(input => {
      const q = input.dataset.question
      corrections[q] = input.value
    })

    this._handleConfirm(corrections)
  }

  /**
   * 渲染模板
   */
  _renderTemplate() {
    return `
      <style>
        #hermes-thinking {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 99999;
          animation: fadeIn 0.2s ease;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .hermes-box {
          background: var(--bg-secondary, #fff);
          border-radius: 16px;
          padding: 24px;
          max-width: 560px;
          width: 90%;
          max-height: 85vh;
          overflow: hidden;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
          animation: slideUp 0.3s ease;
        }

        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .hermes-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 16px;
        }

        .hermes-avatar {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          background: var(--accent-cyan, #0d9488);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;
          animation: pulse 2s infinite;
        }

        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(0.95); opacity: 0.8; }
        }

        .hermes-info { flex: 1; }

        .hermes-title {
          font-size: 1.125rem;
          font-weight: 600;
          color: var(--text-primary, #1c1c1c);
        }

        .hermes-status {
          font-size: 0.875rem;
          color: var(--text-secondary, #666);
        }

        .hermes-thinking-content {
          background: var(--bg-tertiary, #f5f5f5);
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
          font-size: 0.9375rem;
          color: var(--text-primary, #1c1c1c);
          min-height: 60px;
          max-height: 120px;
          overflow-y: auto;
        }

        .hermes-log {
          background: var(--bg-tertiary, #f5f5f5);
          border-radius: 8px;
          padding: 12px;
          max-height: 200px;
          overflow-y: auto;
          margin-bottom: 16px;
        }

        .hermes-log-title {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--text-muted, #999);
          margin-bottom: 8px;
          text-transform: uppercase;
        }

        .hermes-log-list { display: flex; flex-direction: column; gap: 6px; }

        .hermes-log-item {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          font-size: 0.8125rem;
          animation: logSlide 0.2s ease;
        }

        @keyframes logSlide {
          from { opacity: 0; transform: translateX(-10px); }
          to { opacity: 1; transform: translateX(0); }
        }

        .log-icon { flex-shrink: 0; }
        .log-agent { font-weight: 500; color: var(--accent-cyan, #0d9488); flex-shrink: 0; }
        .log-message { color: var(--text-secondary, #666); word-break: break-word; }
        .log-thinking .log-message { font-style: italic; }
        .log-error .log-agent { color: var(--error, #dc2626); }
        .log-complete .log-agent { color: var(--success, #059669); }

        .hermes-footer {
          display: flex;
          gap: 12px;
          justify-content: center;
        }

        .hermes-cancel-btn {
          padding: 10px 32px;
          border: 1px solid var(--border, #ddd);
          border-radius: 8px;
          background: transparent;
          color: var(--text-secondary, #666);
          cursor: pointer;
          font-size: 0.875rem;
          transition: all 0.2s;
        }

        .hermes-cancel-btn:hover {
          background: var(--bg-hover, #f0f0f0);
        }

        .hermes-confirm-modal {
          display: none;
          position: absolute;
          inset: 0;
          background: rgba(0,0,0,0.5);
          padding: 20px;
          overflow-y: auto;
        }

        .hermes-confirm-content {
          background: var(--bg-secondary, #fff);
          border-radius: 12px;
          padding: 20px;
          max-height: 80vh;
          overflow-y: auto;
        }

        .hermes-confirm-btns {
          display: none;
          gap: 12px;
          justify-content: center;
          margin-top: 16px;
        }

        .confirm-section {
          margin-bottom: 16px;
        }

        .confirm-section h4 {
          margin-bottom: 12px;
          color: var(--text-primary);
        }

        .confirm-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 12px;
          background: var(--bg-tertiary);
          border-radius: 6px;
          margin-bottom: 8px;
        }

        .confirm-item.low-confidence {
          border: 1px solid var(--warning, #d97706);
        }

        .q-num { font-weight: 600; min-width: 60px; }
        .q-answer { flex: 1; }
        .warning { color: var(--warning, #d97706); font-size: 0.875rem; }
        .correction-input {
          width: 60px;
          padding: 6px 10px;
          border: 1px solid var(--border);
          border-radius: 4px;
          font-size: 0.875rem;
        }

        .confirm-actions {
          display: flex;
          gap: 12px;
          justify-content: center;
          margin-top: 16px;
        }

        .confirm-warnings {
          background: var(--warning-bg, #fef3c7);
          padding: 12px;
          border-radius: 8px;
          margin-top: 12px;
        }

        .confirm-warnings h4 { color: var(--warning, #d97706); }
        .confirm-warnings p { margin: 4px 0; font-size: 0.875rem; }

        /* 按钮样式 */
        .btn-primary {
          padding: 10px 24px;
          background: var(--accent-cyan, #0d9488);
          color: white;
          border: none;
          border-radius: 8px;
          cursor: pointer;
          font-size: 0.875rem;
          transition: all 0.2s;
        }
        .btn-primary:hover { background: var(--accent-cyan-light, #14b8a6); }

        .btn-secondary {
          padding: 10px 24px;
          background: transparent;
          color: var(--text-secondary);
          border: 1px solid var(--border);
          border-radius: 8px;
          cursor: pointer;
          font-size: 0.875rem;
          transition: all 0.2s;
        }
        .btn-secondary:hover { background: var(--bg-hover); }
      </style>

      <div class="hermes-box">
        <div class="hermes-header">
          <div class="hermes-avatar">🤖</div>
          <div class="hermes-info">
            <div class="hermes-title">Hermes Agent</div>
            <div class="hermes-status">处理中...</div>
          </div>
        </div>

        <div class="hermes-thinking-content">
          正在启动智能分析...
        </div>

        <div class="hermes-log">
          <div class="hermes-log-title">工作日志</div>
          <div class="hermes-log-list"></div>
        </div>

        <div class="hermes-footer">
          <button class="hermes-cancel-btn" id="hermes-cancel">取消任务</button>
        </div>

        <div class="hermes-confirm-modal">
          <div class="hermes-confirm-content"></div>
        </div>

        <div class="hermes-confirm-btns">
          <button class="btn-secondary" onclick="HermesThinking.hide()">取消</button>
          <button class="btn-primary" onclick="HermesThinking.confirm({})">确认</button>
        </div>
      </div>
    `
  }
}

// 全局单例
const HermesThinking = new HermesThinkingManager()

// 快捷方法
function showHermesThinking(options) {
  return HermesThinking.show(options)
}

function updateHermesThinking(event) {
  return HermesThinking.update(event)
}

function hideHermesThinking() {
  return HermesThinking.hide()
}

// 全局挂载
if (typeof window !== 'undefined') {
  window.HermesThinking = HermesThinking
  window.showHermesThinking = showHermesThinking
  window.updateHermesThinking = updateHermesThinking
  window.hideHermesThinking = hideHermesThinking
}

export { HermesThinking, showHermesThinking, updateHermesThinking, hideHermesThinking }
