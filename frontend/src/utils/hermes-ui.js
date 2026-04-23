/**
 * Hermes Agent UI 包装工具
 * 提供简洁的流式调用接口，自动处理 UI 更新
 */

import { hermesService, HermesEventType, TaskType } from '../services/hermes.js'
import { Toast } from '../components/index.js'

// 工具名称映射（用于展示）
const ToolNames = {
  exam_ocr_recognize: 'OCR识别',
  exam_generate: 'AI出题',
  exam_import_questions: '导入真题',
  exam_search_historical: '真题检索',
  diagnosis_barrier_class: '障碍诊断',
  diagnosis_plan_generate: '学习计划生成',
  chemistry_parser: '文档解析(MinerU)',
  chemistry_memory: '记忆检索'
}

// Agent 阶段消息
const PhaseMessages = {
  [TaskType.OCR_RECOGNIZE]: [
    '正在分析图片内容...',
    '定位答题卡区域...',
    '识别学生填涂答案...',
    'LLM语义校验...',
    '生成识别报告...'
  ],
  [TaskType.PDF_PARSE]: [
    '正在接收文档...',
    'MinerU解析中...',
    '提取化学题目...',
    '识别LaTeX公式...',
    '整理题目数据...'
  ],
  [TaskType.GENERATE_QUESTIONS]: [
    '理解题目要求...',
    '检索知识图谱...',
    '分析知识点关联...',
    '生成题目变种...',
    '执行安全审核...',
    '优化题目表述...'
  ],
  [TaskType.ANALYZE_BARRIER]: [
    '分析学生答题数据...',
    '识别错误模式...',
    '诊断障碍类型...',
    '评估障碍等级...',
    '生成诊断报告...'
  ],
  [TaskType.GENERATE_LEARNING_PLAN]: [
    '分析学习历史...',
    '识别薄弱知识点...',
    '匹配干预策略...',
    '生成每日任务...',
    '构建激励方案...',
    '完成学习计划...'
  ],
  [TaskType.GENERATE_REPORT]: [
    '收集学情数据...',
    '分析班级表现...',
    '生成对比图表...',
    '撰写报告文案...',
    '完成报告生成...'
  ]
}

/**
 * 执行 Hermes Agent 任务（带 UI 反馈）
 * @param {string} taskType - 任务类型
 * @param {object} params - 任务参数
 * @param {object} options - UI 选项
 * @returns {Promise<object>} - 最终结果
 */
export async function runHermesTask(taskType, params = {}, options = {}) {
  const {
    onThinking,        // 自定义 thinking 回调
    onToolCall,        // 自定义工具调用回调
    onToolResult,      // 自定义工具结果回调
    onNeedsConfirm,    // 自定义确认回调
    onComplete,        // 完成回调
    onError,           // 错误回调
    startMessage,      // 自定义起始消息
    enableThinking = true,  // 是否显示 thinking 动画
    thinkingEl = null,       // thinking 显示元素
    thinkingLogEl = null    // 日志列表元素
  } = options

  // 重置 thinking 显示
  let thinkingProgress = 0
  let currentToolName = ''

  // 设置回调
  hermesService.on(HermesEventType.THINKING, (event) => {
    if (enableThinking && thinkingEl) {
      thinkingEl.textContent = event.content || getPhaseMessage(taskType, thinkingProgress)
    }
    onThinking?.(event)
  })

  hermesService.on(HermesEventType.TOOL_CALL, (event) => {
    currentToolName = ToolNames[event.tool] || event.tool
    if (thinkingLogEl) {
      addThinkingLog(thinkingLogEl, 'tool', `调用工具: ${currentToolName}`)
    }
    if (enableThinking && thinkingEl) {
      thinkingEl.textContent = `执行 ${currentToolName}...`
    }
    onToolCall?.(event)
  })

  hermesService.on(HermesEventType.TOOL_RESULT, (event) => {
    if (thinkingLogEl) {
      const preview = typeof event.result === 'string'
        ? event.result.substring(0, 50) + '...'
        : JSON.stringify(event.result).substring(0, 50) + '...'
      addThinkingLog(thinkingLogEl, 'result', `工具返回: ${preview}`)
    }
    onToolResult?.(event)
  })

  hermesService.on(HermesEventType.NEEDS_CONFIRMATION, (event) => {
    if (thinkingLogEl) {
      addThinkingLog(thinkingLogEl, 'confirm', '需要人工确认...')
    }
    onNeedsConfirm?.(event)
  })

  hermesService.on(HermesEventType.ERROR, (event) => {
    Toast.error('Agent错误: ' + (event.error || event.message))
    onError?.(event)
  })

  // 启动流式执行
  const streamResult = await hermesService.executeStream(taskType, params)

  if (!streamResult.success) {
    throw new Error(streamResult.error || 'Agent启动失败')
  }

  // 处理流式响应
  return new Promise((resolve, reject) => {
    hermesService.on(HermesEventType.FINAL, (event) => {
      if (thinkingLogEl) {
        addThinkingLog(thinkingLogEl, 'complete', '任务完成 ✓')
      }
      onComplete?.(event)
      resolve(event.result || event)
    })

    hermesService.processStream(streamResult.reader, (event) => {
      // 更新 thinking 进度
      if (event.type === HermesEventType.THINKING) {
        thinkingProgress = Math.min(thinkingProgress + 0.1, 0.9)
      }
    }).catch(reject)
  })
}

/**
 * 获取阶段性消息
 */
function getPhaseMessage(taskType, progress) {
  const messages = PhaseMessages[taskType] || ['处理中...']
  const index = Math.min(Math.floor(progress * messages.length), messages.length - 1)
  return messages[index]
}

/**
 * 添加 thinking 日志
 */
function addThinkingLog(container, type, message) {
  const logEl = document.createElement('div')
  logEl.className = `agent-log-item log-${type}`
  logEl.innerHTML = `
    <span class="log-icon">${getLogIcon(type)}</span>
    <span class="log-message">${message}</span>
  `
  container.appendChild(logEl)
  container.scrollTop = container.scrollHeight
}

/**
 * 获取日志图标
 */
function getLogIcon(type) {
  const icons = {
    thinking: '🤔',
    tool: '⚡',
    result: '📋',
    confirm: '⚠️',
    complete: '✓',
    error: '❌'
  }
  return icons[type] || '•'
}

/**
 * 取消 Hermes Agent 任务
 */
export function cancelHermesTask() {
  hermesService.cancel()
}

/**
 * 中断 Hermes Agent 任务
 */
export function interruptHermesTask() {
  hermesService.interrupt()
}

/**
 * 获取当前待确认数据
 */
export function getPendingConfirm() {
  return hermesService.getPendingConfirm()
}

/**
 * 确认修正
 */
export async function confirmCorrection(corrections = {}) {
  return await hermesService.confirm(corrections)
}
