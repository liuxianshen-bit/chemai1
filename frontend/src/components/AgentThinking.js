/**
 * Agent工作过程展示组件
 */

const AgentIcons = {
  chemistry_exam: '📝',
  chemistry_diagnosis: '🔬',
  chemistry_parser: '📷',
  chemistry_memory: '🧠',
  chemistry_notification: '🔔',
  chemistry_improvement: '📈',
  thinking: '🤔',
  acting: '⚡',
  observing: '👁️'
}

const AgentNames = {
  chemistry_exam: '出题Agent',
  chemistry_diagnosis: '诊断Agent',
  chemistry_parser: 'OCR解析Agent',
  chemistry_memory: '记忆Agent',
  chemistry_notification: '通知Agent',
  chemistry_improvement: '改进Agent'
}

class AgentThinkingManager {
  constructor() {
    this.currentAgent = null
    this.logs = []
    this.container = null
    this.onComplete = null
  }

  /**
   * 显示Agent思考中
   */
  show(options = {}) {
    const {
      agent = 'chemistry_exam',
      message = 'AI正在思考中...',
      showLog = true,
      onComplete = null
    } = options

    this.currentAgent = agent
    this.logs = []
    this.onComplete = onComplete

    // 移除已存在的
    this.hide()

    // 创建容器
    this.container = document.createElement('div')
    this.container.id = 'agent-thinking'
    this.container.innerHTML = this.renderTemplate()
    document.body.appendChild(this.container)

    // 添加欢迎日志
    this.addLog(agent, '启动', `${AgentNames[agent] || agent} 开始工作`)

    return this
  }

  /**
   * 更新状态
   */
  update(status) {
    if (!this.container) return this

    const { phase, message, progress } = status

    // 更新图标
    const iconEl = this.container.querySelector('.agent-thinking-icon')
    if (iconEl) {
      iconEl.textContent = AgentIcons[phase] || AgentIcons.thinking
    }

    // 更新消息
    const messageEl = this.container.querySelector('.agent-thinking-message')
    if (messageEl) {
      messageEl.textContent = message
    }

    // 更新进度
    const progressEl = this.container.querySelector('.agent-thinking-progress-fill')
    if (progressEl && progress !== undefined) {
      progressEl.style.width = `${progress * 100}%`
    }

    // 添加日志
    if (this.currentAgent && message) {
      this.addLog(this.currentAgent, phase, message)
    }

    return this
  }

  /**
   * 添加日志
   */
  addLog(agent, phase, message) {
    this.logs.push({ agent, phase, message, time: Date.now() })

    if (!this.container) return

    const logList = this.container.querySelector('.agent-log-list')
    if (logList) {
      const logEl = document.createElement('div')
      logEl.className = 'agent-log-item'
      logEl.innerHTML = `
        <span class="log-icon">${AgentIcons[phase] || AgentIcons.thinking}</span>
        <span class="log-agent">${AgentNames[agent] || agent}</span>
        <span class="log-message">${message}</span>
      `
      logList.appendChild(logEl)
      logList.scrollTop = logList.scrollHeight
    }
  }

  /**
   * 完成
   */
  complete(result = {}) {
    if (this.currentAgent) {
      this.addLog(this.currentAgent, 'acting', '任务完成 ✓')
    }

    // 隐藏容器
    setTimeout(() => {
      this.hide()
      if (this.onComplete) {
        this.onComplete(result)
      }
    }, 500)

    return this
  }

  /**
   * 失败
   */
  error(message) {
    if (this.currentAgent) {
      this.addLog(this.currentAgent, 'error', `错误: ${message}`)
    }

    setTimeout(() => {
      this.hide()
    }, 1500)

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
    this.currentAgent = null
    this.logs = []
  }

  /**
   * 渲染模板
   */
  renderTemplate() {
    return `
      <style>
        #agent-thinking {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.7);
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

        .agent-thinking-box {
          background: var(--bg-secondary, #fff);
          border-radius: 16px;
          padding: 24px;
          max-width: 480px;
          width: 90%;
          max-height: 80vh;
          overflow: hidden;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
          animation: slideUp 0.3s ease;
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .agent-thinking-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 16px;
        }

        .agent-thinking-icon {
          font-size: 2rem;
          animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(0.95); }
        }

        .agent-thinking-info {
          flex: 1;
        }

        .agent-thinking-title {
          font-size: 1.125rem;
          font-weight: 600;
          color: var(--text-primary, #1c1c1c);
        }

        .agent-thinking-message {
          font-size: 0.875rem;
          color: var(--text-secondary, #666);
        }

        .agent-thinking-progress {
          height: 6px;
          background: var(--bg-tertiary, #f0f0f0);
          border-radius: 3px;
          margin-bottom: 16px;
          overflow: hidden;
        }

        .agent-thinking-progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #0d9488, #14b8a6);
          border-radius: 3px;
          transition: width 0.3s ease;
          width: 0%;
        }

        .agent-log {
          background: var(--bg-tertiary, #f5f5f5);
          border-radius: 8px;
          padding: 12px;
          max-height: 200px;
          overflow-y: auto;
        }

        .agent-log-title {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--text-muted, #999);
          margin-bottom: 8px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .agent-log-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .agent-log-item {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          font-size: 0.8125rem;
          animation: logSlide 0.2s ease;
        }

        @keyframes logSlide {
          from {
            opacity: 0;
            transform: translateX(-10px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        .log-icon {
          flex-shrink: 0;
        }

        .log-agent {
          font-weight: 500;
          color: var(--accent-cyan, #0d9488);
          flex-shrink: 0;
        }

        .log-message {
          color: var(--text-secondary, #666);
          word-break: break-word;
        }

        .agent-thinking-footer {
          margin-top: 16px;
          text-align: center;
        }

        .agent-cancel-btn {
          padding: 8px 24px;
          border: 1px solid var(--border-default, #ddd);
          border-radius: 8px;
          background: transparent;
          color: var(--text-secondary, #666);
          cursor: pointer;
          font-size: 0.875rem;
          transition: all 0.2s;
        }

        .agent-cancel-btn:hover {
          background: var(--bg-hover, #f0f0f0);
        }
      </style>

      <div class="agent-thinking-box">
        <div class="agent-thinking-header">
          <span class="agent-thinking-icon">🤖</span>
          <div class="agent-thinking-info">
            <div class="agent-thinking-title">AI Agent 工作中</div>
            <div class="agent-thinking-message">请稍候...</div>
          </div>
        </div>

        <div class="agent-thinking-progress">
          <div class="agent-thinking-progress-fill"></div>
        </div>

        <div class="agent-log">
          <div class="agent-log-title">工作日志</div>
          <div class="agent-log-list"></div>
        </div>

        <div class="agent-thinking-footer">
          <button class="agent-cancel-btn" onclick="AgentThinking.hide()">取消</button>
        </div>
      </div>
    `
  }
}

// 全局单例
const AgentThinking = new AgentThinkingManager()

// 快捷方法
function showAgentThinking(options) {
  return AgentThinking.show(options)
}

function updateAgentThinking(status) {
  return AgentThinking.update(status)
}

function hideAgentThinking() {
  return AgentThinking.hide()
}

// 带Agent展示的API调用封装
async function callAgentApi(agentType, apiCall, options = {}) {
  const {
    startMessage = 'AI正在分析...',
    completeMessage = '处理完成'
  } = options

  showAgentThinking({
    agent: agentType,
    message: startMessage
  })

  // 模拟分阶段更新
  let progress = 0
  const progressInterval = setInterval(() => {
    progress = Math.min(progress + Math.random() * 0.15, 0.9)
    updateAgentThinking({
      phase: 'thinking',
      message: getThinkingMessage(agentType, progress),
      progress
    })
  }, 500)

  try {
    const result = await apiCall()

    clearInterval(progressInterval)
    AgentThinking.update({ phase: 'acting', message: completeMessage, progress: 1 })
    AgentThinking.complete(result)

    return result
  } catch (error) {
    clearInterval(progressInterval)
    AgentThinking.error(error.message)
    throw error
  }
}

function getThinkingMessage(agentType, progress) {
  const messages = {
    chemistry_exam: [
      '理解题目要求...',
      '检索知识图谱...',
      '分析知识点关联...',
      '生成题目变种...',
      '执行四维安全审核...',
      '优化题目表述...'
    ],
    chemistry_diagnosis: [
      '分析学生答题数据...',
      '识别错误模式...',
      '诊断障碍类型...',
      '评估障碍等级...',
      '生成诊断报告...'
    ],
    chemistry_parser: [
      '接收图片数据...',
      '执行OCR识别...',
      '校正识别结果...',
      'LLM语义分析...',
      '提取答案信息...'
    ],
    chemistry_improvement: [
      '分析学习数据...',
      '识别薄弱环节...',
      '生成个性化建议...',
      '优化学习路径...'
    ]
  }

  const agentMessages = messages[agentType] || ['处理中...']
  const index = Math.min(Math.floor(progress * agentMessages.length), agentMessages.length - 1)
  return agentMessages[index]
}

// 导出
export { AgentThinking, showAgentThinking, updateAgentThinking, hideAgentThinking, callAgentApi }

// 全局挂载
if (typeof window !== 'undefined') {
  window.AgentThinking = AgentThinking
  window.showAgentThinking = showAgentThinking
  window.updateAgentThinking = updateAgentThinking
  window.hideAgentThinking = hideAgentThinking
  window.callAgentApi = callAgentApi
}
