/**
 * Hermes Agent Service
 * 前端与 Hermes Agent 的交互层
 * 适配 Hermes Agent 的 OpenAI SSE 事件格式
 *
 * 主要变更 (v2):
 * - 重构 _processSSEvent() 适配 OpenAI chat.completion.chunk 格式
 * - 重构 processStream() 支持 SSE event: 格式行
 * - 更新 _buildPrompt() 提供更明确的 Tool 调用指令
 */

import { api, handleApiError } from './api.js'

// ChemAgent API 配置 — 通过 Vite proxy 转发
const AGENT_API = '/api/agent'
// 保留兼容 Hermes 任务管理 API（confirm/correct/interrupt 暂不可用，返回占位）
const HERMES_API = '/api/agent'

// 事件类型
export const HermesEventType = {
  THINKING: 'thinking',           // AI思考/输出内容
  TOOL_CALL: 'tool_call',       // 工具调用
  TOOL_RESULT: 'tool_result',   // 工具执行结果
  NEEDS_CONFIRMATION: 'needs_confirmation', // 需要人工确认
  CONFIRMED: 'confirmed',       // 已确认
  ERROR: 'error',               // 错误
  FINAL: 'final',               // 最终结果
  INTERRUPTED: 'interrupted',    // 已中断
  ROLE: 'role',                  // 角色声明
  TOOL_STARTED: 'tool_started',  // 工具开始执行
  TOOL_COMPLETED: 'tool_completed' // 工具执行完成
}

// 确认类型
export const ConfirmType = {
  OCR_PREVIEW: 'ocr_preview',         // OCR识别预览确认
  PDF_PARSE: 'pdf_parse',              // PDF解析结果确认 (MinerU)
  QUESTION_AUDIT: 'question_audit',   // 题目审核确认
  LEARNING_PLAN: 'learning_plan',     // 学习计划确认
  REPORT_GENERATE: 'report_generate'  // 报告生成确认
}

// Task 类型
export const TaskType = {
  // 识别类
  OCR_RECOGNIZE: 'ocr_recognize',           // OCR识别答题卡
  PDF_PARSE: 'pdf_parse',                   // PDF解析 (MinerU)
  MULTIMODAL_ANALYSIS: 'multimodal_analysis', // 视觉模型分析（复杂图片）

  // 出题类
  GENERATE_QUESTIONS: 'generate_questions',   // AI出题
  IMPORT_QUESTIONS: 'import_questions',       // 导入真题

  // 手动选题类
  SEARCH_HISTORICAL: 'search_historical',     // 查询历年真题

  // 服务状态类
  GET_SERVICES_STATUS: 'get_services_status', // 获取解析服务状态

  // 诊断类
  ANALYZE_BARRIER: 'analyze_barrier',        // 学情分析
  GENERATE_LEARNING_PLAN: 'generate_learning_plan', // 学习计划

  // 报告类
  GENERATE_REPORT: 'generate_report'          // 生成报告
}

// 化学工具名称映射 (用于识别 Tool call)
const CHEMISTRY_TOOLS = {
  // chemistry_parser 工具
  'parse_pdf_questions': 'PDF解析',
  'parse_docx_questions': 'Word解析',
  'parse_image_chemical': '图片化学式识别',
  'standardize_chemical_formula': '化学公式标准化',
  'classify_question_type': '题目类型分类',
  'extract_answer_from_ocr': 'OCR答案提取',
  'batch_parse_documents': '批量文档解析',
  'get_mineru_status': 'MinerU状态',
  'smart_parse_document': '智能文档解析',      // 新增：自动选择OCR/MinerU/Vision
  'import_question_bank': '上传真题',          // 新增：上传真题到题库
  'get_services_status': '解析服务状态',      // 新增：获取所有服务可用性
  // chemistry_exam 工具
  'exam_generate': 'AI出题',
  'exam_audit': '题目审核',
  'exam_search_historical': '真题检索',
  'exam_get_exam_sets': '获取真题集',
  'exam_get_exam_set_detail': '真题集详情',
  'exam_find_similar': '相似真题',
  'exam_manual_select': '手动选题',
  'exam_import': '题目导入',
  'exam_import_ocr': 'OCR导入真题',
  'exam_balance_check': '方程式配平检查',
  // chemistry_diagnosis 工具
  'diagnosis_barrier_class': '班级障碍诊断',
  'diagnosis_barrier_student': '学生障碍详情',
  'diagnosis_plan_generate': '学习计划生成',
  'diagnosis_plan_apply': '应用学习计划',
  'diagnosis_plan_send_parent': '发送学习计划',
  'diagnosis_config_get': '获取诊断配置',
  'diagnosis_config_update': '更新诊断配置'
}

class HermesAgentService {
  constructor() {
    this.currentRunId = null
    this.eventSource = null
    this.callbacks = {
      onThinking: null,
      onToolCall: null,
      onToolResult: null,
      onNeedsConfirmation: null,
      onConfirmed: null,
      onError: null,
      onFinal: null,
      onInterrupted: null,
      onRole: null,
      onToolStarted: null,
      onToolCompleted: null
    }
    this.pendingConfirm = null  // 当前待确认的数据
    this.abortController = null
    this._accumulatedContent = ''  // 累积的内容片段
    this._toolCallsBuffer = []      // Tool calls 缓冲
  }

  /**
   * 设置事件回调
   */
  on(eventType, callback) {
    this.callbacks[eventType] = callback
    return this
  }

  /**
   * 执行 Agent 任务（异步方式，获取 run_id）
   */
  async execute(task, params = {}) {
    try {
      const response = await fetch(`${HERMES_API}/runs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: 'hermes-agent',
          input: {
            role: 'user',
            content: this._buildPrompt(task, params)
          }
        })
      })

      if (!response.ok) {
        throw new Error(`Agent启动失败: ${response.status}`)
      }

      const data = await response.json()
      this.currentRunId = data.run_id

      return {
        success: true,
        run_id: data.run_id
      }
    } catch (error) {
      return {
        success: false,
        error: error.message
      }
    }
  }

  /**
   * 执行 Agent 任务（同步方式，流式返回）- 使用 /chat/completions
   */
  async executeStream(task, params = {}) {
    this.abortController = new AbortController()
    this._resetState()

    try {
      const response = await fetch(`${AGENT_API}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          persona: this._getPersona(task),
          message: this._buildPrompt(task, params),
          provider: 'deepseek',
          history: params.conversationHistory || []
        }),
        signal: this.abortController.signal
      })

      if (!response.ok) {
        throw new Error(`Agent调用失败: ${response.status}`)
      }

      // 返回流式reader供外部处理
      return {
        success: true,
        reader: response.body.getReader(),
        cancel: () => this.abortController?.abort()
      }
    } catch (error) {
      return {
        success: false,
        error: error.message
      }
    }
  }

  /**
   * 重置状态
   */
  _resetState() {
    this._accumulatedContent = ''
    this._toolCallsBuffer = []
    this.pendingConfirm = null
  }

  /**
   * 根据任务类型映射 Persona
   */
  _getPersona(task) {
    const taskPersonaMap = {
      'generate_questions': 'teacher',
      'audit_question': 'teacher',
      'diagnose_barrier': 'teacher',
      'analyze_barrier': 'teacher',
      'generate_learning_plan': 'teacher',
      'ocr_recognize': 'teacher',
      'ocr_parse': 'teacher',
      'chemistry_tutor': 'tutor',
      'simulate_experiment': 'tutor',
      'weekly_report': 'parent',
    }
    return taskPersonaMap[task] || 'tutor'
  }

  /**
   * 监听 SSE 事件流（用于 /runs 方式）
   */
  async listenToEvents(runId, onEvent) {
    return new Promise((resolve, reject) => {
      const eventSource = new EventSource(`${HERMES_API}/runs/${runId}/events`)
      this.eventSource = eventSource

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onEvent(data)

          // 处理不同类型的事件
          switch (data.type) {
            case 'thinking':
              this.callbacks.onThinking?.(data)
              break
            case 'tool_call':
              this.callbacks.onToolCall?.(data)
              break
            case 'tool_result':
              this.callbacks.onToolResult?.(data)
              break
            case 'needs_confirmation':
              this.pendingConfirm = data
              this.callbacks.onNeedsConfirmation?.(data)
              break
            case 'confirmed':
              this.pendingConfirm = null
              this.callbacks.onConfirmed?.(data)
              break
            case 'error':
              this.callbacks.onError?.(data)
              break
            case 'final':
            case 'done':
              eventSource.close()
              this.callbacks.onFinal?.(data)
              resolve(data)
              break
            case 'interrupted':
              this.callbacks.onInterrupted?.(data)
              break
          }
        } catch (e) {
          console.warn('事件解析失败:', e, event.data)
        }
      }

      eventSource.onerror = (error) => {
        eventSource.close()
        reject(error)
      }
    })
  }

  /**
   * 处理 SSE 流式响应（用于 /chat/completions 方式）
   * 重构以适配 OpenAI SSE 格式和 Hermes 自定义事件格式
   */
  async processStream(reader, onEvent) {
    const decoder = new TextDecoder()
    let buffer = ''
    let pendingEventType = null  // 跟踪前一个 event: 行

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // 保留未完成的行

        for (const line of lines) {
          // 处理 SSE event: 行 (Hermes 自定义事件类型)
          if (line.startsWith('event:')) {
            pendingEventType = line.slice(6).trim()
            continue
          }

          // 处理 SSE data: 行
          if (line.startsWith('data:')) {
            const dataStr = line.slice(5).trim()

            // 处理 [DONE]
            if (dataStr === '[DONE]') {
              // 如果有累积的内容，发送最后的 final 事件
              if (this._accumulatedContent) {
                this.callbacks.onFinal?.({
                  type: HermesEventType.FINAL,
                  content: this._accumulatedContent
                })
              }
              return
            }

            try {
              const data = JSON.parse(dataStr)

              // 根据前一个 event: 行决定如何处理
              if (pendingEventType === 'hermes.tool.progress') {
                await this._processToolProgress(data, onEvent)
              } else if (data.object === 'chat.completion.chunk') {
                // OpenAI 标准 SSE 格式
                await this._processOpenAIChunk(data, onEvent)
              } else if (data.event === 'run.completed') {
                // /v1/runs 方式的最终结果
                this.callbacks.onFinal?.({
                  type: HermesEventType.FINAL,
                  result: data.output
                })
                return
              } else if (data.event === 'run.failed') {
                this.callbacks.onError?.({
                  type: HermesEventType.ERROR,
                  error: data.error
                })
                return
              } else if (data.event === 'message.delta') {
                // /v1/runs 方式的消息增量
                if (data.delta) {
                  const event = {
                    type: HermesEventType.THINKING,
                    content: data.delta
                  }
                  this._accumulatedContent += data.delta
                  onEvent(event)
                  this.callbacks.onThinking?.(event)
                }
              }

            } catch (e) {
              console.warn('SSE解析失败:', e)
            }

            // 重置 pending event type
            pendingEventType = null
          }
        }
      }
    } catch (error) {
      this.callbacks.onError?.({ error: error.message })
    }
  }

  /**
   * 处理 OpenAI chat.completion.chunk 格式的事件
   * Hermes Agent 的 /v1/chat/completions 发送的 SSE 格式
   */
  async _processOpenAIChunk(data, onEvent) {
    const delta = data.choices?.[0]?.delta
    const finishReason = data.choices?.[0]?.finish_reason

    if (!delta) return

    // 1. 处理角色声明
    if (delta.role) {
      const event = {
        type: 'role',
        role: delta.role
      }
      onEvent(event)
      this.callbacks.onRole?.(event)
    }

    // 2. 处理内容片段
    if (delta.content) {
      this._accumulatedContent += delta.content
      const event = {
        type: HermesEventType.THINKING,
        content: delta.content,
        accumulated: this._accumulatedContent
      }
      onEvent(event)
      this.callbacks.onThinking?.(event)
    }

    // 3. 处理 Tool Calls (OpenAI function calling 格式)
    if (delta.tool_calls) {
      for (const toolCall of delta.tool_calls) {
        if (toolCall.function) {
          // 累积 function.arguments
          const existingCall = this._toolCallsBuffer.find(
            tc => tc.index === toolCall.index
          )

          if (existingCall) {
            // 追加参数
            existingCall.arguments += toolCall.function.arguments || ''
            existingCall.name = toolCall.function.name || existingCall.name
          } else {
            // 新建 tool call
            this._toolCallsBuffer.push({
              index: toolCall.index,
              id: toolCall.id,
              name: toolCall.function.name,
              arguments: toolCall.function.arguments || ''
            })
          }
        }
      }
    }

    // 4. 处理 finish_reason
    if (finishReason === 'stop') {
      // Agent 结束输出，如果有未发送的 tool calls，先发送
      await this._flushToolCalls(onEvent)

      const event = {
        type: HermesEventType.FINAL,
        content: this._accumulatedContent,
        finishReason: 'stop'
      }
      onEvent(event)
      this.callbacks.onFinal?.(event)
    } else if (finishReason === 'tool_calls') {
      // Agent 请求调用工具，发送所有累积的 tool calls
      await this._flushToolCalls(onEvent)
    }
  }

  /**
   * 发送所有累积的 tool calls
   */
  async _flushToolCalls(onEvent) {
    for (const tc of this._toolCallsBuffer) {
      let params = {}
      try {
        params = JSON.parse(tc.arguments || '{}')
      } catch (e) {
        console.warn('解析 tool call arguments 失败:', e)
      }

      const event = {
        type: HermesEventType.TOOL_CALL,
        tool: tc.name,
        params: params,
        toolCallId: tc.id,
        toolIndex: tc.index
      }

      onEvent(event)
      this.callbacks.onToolCall?.(event)
    }
    this._toolCallsBuffer = []
  }

  /**
   * 处理 hermes.tool.progress 格式事件
   * Hermes Agent 自定义的 tool 执行进度事件
   */
  async _processToolProgress(data, onEvent) {
    // hermes.tool.progress 事件格式:
    // {"tool": "parse_pdf_questions", "emoji": "📄", "label": "正在解析PDF..."}
    // {"event": "tool.started", "tool": "xxx", ...}
    // {"event": "tool.completed", "tool": "xxx", "duration": 1.23, "error": false}

    const eventType = data.event
    const toolName = data.tool
    const toolLabel = data.label || CHEMISTRY_TOOLS[toolName] || toolName

    if (eventType === 'tool.started') {
      const event = {
        type: HermesEventType.TOOL_STARTED,
        tool: toolName,
        label: toolLabel,
        preview: data.preview
      }
      onEvent(event)
      this.callbacks.onToolStarted?.(event)
    } else if (eventType === 'tool.completed') {
      const event = {
        type: HermesEventType.TOOL_COMPLETED,
        tool: toolName,
        duration: data.duration,
        hasError: data.error
      }
      onEvent(event)
      this.callbacks.onToolCompleted?.(event)
    } else if (data.tool) {
      // 旧格式的 tool progress
      const event = {
        type: HermesEventType.TOOL_STARTED,
        tool: toolName,
        label: toolLabel,
        emoji: data.emoji
      }
      onEvent(event)
      this.callbacks.onToolStarted?.(event)
    }
  }

  /**
   * 处理单个 SSE 事件（旧版本兼容）
   */
  async _processSSEvent(data, onEvent) {
    // OpenAI chat.completion.chunk 格式
    if (data.object === 'chat.completion.chunk') {
      await this._processOpenAIChunk(data, onEvent)
      return
    }

    // Hermes 自定义事件
    if (data.event === 'hermes.tool.progress') {
      await this._processToolProgress(data, onEvent)
      return
    }

    // 处理 delta 事件（旧版本兼容）
    if (data.type === 'chunk' || data.type === 'content_chunk') {
      const content = data.delta?.content || data.content || ''
      if (content) {
        const event = {
          type: HermesEventType.THINKING,
          content: content
        }
        onEvent(event)
        this.callbacks.onThinking?.(event)
      }
    }

    // 处理工具调用
    if (data.type === 'tool_call' || data.tool_calls) {
      const event = {
        type: HermesEventType.TOOL_CALL,
        tool: data.tool_call?.name || data.tool_calls?.[0]?.name,
        params: data.tool_call?.input || data.tool_calls?.[0]?.input
      }
      onEvent(event)
      this.callbacks.onToolCall?.(event)
    }

    // 处理工具结果
    if (data.type === 'tool_result' || data.tool_result) {
      const event = {
        type: HermesEventType.TOOL_RESULT,
        result: data.tool_result?.content || data.result
      }
      onEvent(event)
      this.callbacks.onToolResult?.(event)
    }

    // 处理需要确认
    if (data.needs_confirmation || data.type === 'waiting_confirmation') {
      this.pendingConfirm = data
      const event = {
        type: HermesEventType.NEEDS_CONFIRMATION,
        confirmType: data.confirm_type || ConfirmType.OCR_PREVIEW,
        data: data.confirm_data || data
      }
      onEvent(event)
      this.callbacks.onNeedsConfirmation?.(event)
    }

    // 处理最终结果
    if (data.type === 'final' || data.type === 'done' || data.is_final) {
      const event = {
        type: HermesEventType.FINAL,
        result: data.result || data
      }
      onEvent(event)
      this.callbacks.onFinal?.(event)
    }
  }

  /**
   * 发送确认（用于 HITL）
   */
  async confirm(corrections = {}, comment = '') {
    if (!this.currentRunId) {
      return { success: false, error: 'No active run' }
    }

    try {
      const response = await fetch(`${HERMES_API}/runs/${this.currentRunId}/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          corrections,
          comment
        })
      })

      const data = await response.json()

      this.callbacks.onConfirmed?.({
        type: 'confirmed',
        corrections
      })

      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  /**
   * 发送修正（用于 HITL 修正模式）
   */
  async correct(corrections) {
    if (!this.currentRunId) {
      return { success: false, error: 'No active run' }
    }

    try {
      const response = await fetch(`${HERMES_API}/runs/${this.currentRunId}/correct`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(corrections)
      })

      const data = await response.json()
      this.pendingConfirm = null

      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  /**
   * 打断 Agent 执行
   */
  async interrupt() {
    if (!this.currentRunId) return

    try {
      await fetch(`${HERMES_API}/runs/${this.currentRunId}/interrupt`, {
        method: 'POST'
      })
      this.abortController?.abort()
      this.eventSource?.close()
    } catch (error) {
      console.warn('打断失败:', error)
    }
  }

  /**
   * 取消任务
   */
  cancel() {
    this.abortController?.abort()
    this.eventSource?.close()
    this.currentRunId = null
    this.pendingConfirm = null
    this._resetState()
  }

  /**
   * 获取当前待确认数据
   */
  getPendingConfirm() {
    return this.pendingConfirm
  }

  /**
   * 构建 Prompt - 提供更明确的 Tool 调用指令
   */
  _buildPrompt(task, params) {
    // Tool 调用指令 - 明确告诉 LLM 应该调用哪个工具
    const toolInstructions = {
      [TaskType.OCR_RECOGNIZE]: `请分析这张答题卡图片，识别每个学生的答案。

重要：请使用 smart_parse_document 智能文档解析工具来识别图片内容。
该工具会自动选择最佳解析方式（OCR → 视觉模型降级）。

返回格式：
- 学生ID和答案列表
- 每个答案的置信度
- 低置信度答案请标记

用户提供的参数：
${params.image ? `图片数据: ${params.image.substring(0, 100)}...` : '无图片数据'}`,

      [TaskType.PDF_PARSE]: `请解析这个PDF/Word文档，提取其中的化学题目。

重要：请使用 parse_pdf_questions 工具来解析文档。
支持的格式：PDF (.pdf), Word (.docx)
MinerU 会自动识别 LaTeX 化学公式。

用户参数：
- 文件路径: ${params.file_path || '未提供'}
- 语言: ${params.lang || 'ch (中文)'}
- 页码范围: ${params.start_page || 0} - ${params.end_page || '结束'}

请提取所有化学相关题目，包括：
- 选择题、填空题、计算题、简答题
- 化学方程式
- 实验题目`,

      [TaskType.GENERATE_QUESTIONS]: `请为学生生成化学练习题目。

重要：请使用 exam_generate 工具来生成题目。
该工具会调用 AI 生成题目，并进行四维安全审核（政治安全、科学性、难度适宜性、格式规范性）。

用户参数：
- 知识点: ${params.knowledge_points?.join('、') || '未指定'}
- 难度: ${params.difficulty || 'medium (中等)'}
  可选值: easy (简单), medium (中等), hard (困难), competition (竞赛)
- 题目数量: ${params.quantity || 10} 道
- 考试类型: ${params.exam_type || '单元练习'}
  可选值: 单元练习, 期中考试, 期末考试, 高考模拟

请确保：
1. 优先从历年真题库检索相似题目
2. 基于真题生成变种题
3. 涵盖指定的知识点`,

      [TaskType.IMPORT_QUESTIONS]: `请将题目导入到真题库。

重要：请使用 smart_parse_document 智能解析文档，然后使用 import_question_bank 导入到题库。
该工具会自动：
1. 识别文件类型（PDF/图片/文档）
2. 选择最佳解析方式（MinerU/OCR/视觉模型）
3. 提取题目内容
4. 导入到真题库

用户参数：
- 来源: ${params.source_name || params.source || '手动导入'}
- 年份: ${params.year || new Date().getFullYear()}
- 地区: ${params.region || '通用'}
- 格式: ${params.format || params.file_type || 'auto'}

请处理导入的题目并返回导入结果。`,

      [TaskType.ANALYZE_BARRIER]: `请分析这次考试的学情数据，进行班级障碍类型诊断。

重要：请使用 diagnosis_barrier_class 工具进行诊断。
该工具会分析学生的答题情况，识别三种障碍类型：
1. 概念理解型 (concept) - 对化学概念理解不清
2. 审题障碍型 (reading) - 读不懂题目意思
3. 表述障碍型 (expression) - 知道答案但表述不规范

用户参数：
- 班级ID: ${params.class_id || '未提供'}
- 考试记录ID: ${params.exam_record_id || '未提供'}

请返回：
- 班级障碍类型分布统计
- 每个学生的障碍类型详情
- 重点关注学生名单`,

      [TaskType.GENERATE_LEARNING_PLAN]: `请为学生生成个性化的学习计划。

重要：请使用 diagnosis_plan_generate 工具生成学习计划。
该工具会根据学生的障碍类型和薄弱知识点，生成针对性干预策略。

用户参数：
- 学生ID: ${params.student_id || '未提供'}
- 障碍类型: ${params.barrier_type || '未指定'}
  可选值: concept (概念理解型), reading (审题障碍型), expression (表述障碍型)
- 薄弱知识点: ${params.weak_knowledge_points?.join('、') || '未指定'}
${params.recent_performance ? `- 近期表现数据: ${JSON.stringify(params.recent_performance).substring(0, 100)}...` : ''}

请生成学习计划，包含：
1. 每日学习任务
2. 每周学习目标
3. 针对性干预策略
4. 家长通知内容（可选）`,

      [TaskType.GENERATE_REPORT]: `请生成学情报告。

重要：请首先调用 diagnosis_barrier_class 获取班级诊断结果，然后汇总生成报告。

报告应包含：
1. 班级整体分析
   - 班级平均分、及格率、优秀率
   - 障碍类型分布饼图数据
   - 与上次考试对比

2. 每个学生的学习情况
   - 个人成绩和排名
   - 障碍类型
   - 薄弱知识点

3. 教学建议
   - 针对班级共性问题的教学策略
   - 针对个体学生的辅导建议

用户参数：
- 班级ID: ${params.class_id || '未提供'}
- 考试记录ID: ${params.exam_record_id || '未提供'}`,

      [TaskType.SEARCH_HISTORICAL]: `请从历年真题库中检索符合条件的真题。

重要：请使用 exam_search_historical 工具检索历年真题。

用户参数：
- 来源/地区: ${params.region || params.source || '全部'}
- 年份: ${params.year || '全部'}
- 知识点: ${params.knowledge_point || params.knowledge_points || '全部'}
- 难度: ${params.difficulty || '全部'}
- 关键词: ${params.keyword || '无'}

请返回检索到的真题列表，每道题目包含：
- 题目ID
- 题目内容
- 答案
- 知识点
- 难度
- 来源和年份`,

      [TaskType.GET_SERVICES_STATUS]: `请获取所有解析服务的可用性状态。

重要：请使用 get_services_status 工具获取服务状态。

该工具会检查以下服务的可用性：
1. OCR - 文字识别服务（智谱GLM-OCR）
2. MinerU - 文档解析服务（Magic-Doc）
3. 视觉模型 - 多模态AI模型（智谱GLM-4V）

请返回每个服务的：
- available: 是否可用
- provider: 服务提供商
- note: 额外说明（如有）`
    }

    return toolInstructions[task] || task
  }
}

// 导出单例
export const hermesService = new HermesAgentService()

export default hermesService
