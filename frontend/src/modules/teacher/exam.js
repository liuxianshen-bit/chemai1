/**
 * 教师端 - 考试管理模块
 * 包含AI生成题目、手动选题、导入真题三大功能
 */
import { examService } from '../../services/index.js'
import { hermesService, TaskType } from '../../services/hermes.js'
import { Toast, showLoading, hideLoading, showHermesThinking, hideHermesThinking } from '../../components/index.js'

// 全局状态
let currentExam = null
let currentExamList = []
let currentTab = 'ai' // 当前Tab: ai, manual, import
let selectedQuestions = [] // 已选题目列表
let historicalQuestions = [] // 历史真题列表
let currentFilter = {
  region: 'all',
  year: 'all',
  knowledge_point: 'all',
  difficulty: 'all'
}

// 导入真题状态
let importState = {
  step: 1, // 1:选择文件, 2:解析中, 3:预览结果, 4:选择真题集, 5:确认导入
  fileData: null,
  parsedResult: null,
  targetSetId: null
}

/**
 * 初始化考试模块
 */
export async function initExamModule() {
  const container = document.getElementById('exam-list')
  if (!container) return

  // 渲染Tab容器
  renderExamTabs()

  // 根据当前Tab加载内容
  switchTab(currentTab)
}

/**
 * 渲染考试管理Tab
 */
function renderExamTabs() {
  const container = document.getElementById('exam-list')
  if (!container) return

  container.innerHTML = `
    <div class="exam-tabs">
      <button class="exam-tab ${currentTab === 'ai' ? 'active' : ''}" data-tab="ai">
        <span class="tab-icon">📝</span>
        <span class="tab-text">AI生成题目</span>
      </button>
      <button class="exam-tab ${currentTab === 'manual' ? 'active' : ''}" data-tab="manual">
        <span class="tab-icon">📚</span>
        <span class="tab-text">手动选题</span>
      </button>
      <button class="exam-tab ${currentTab === 'import' ? 'active' : ''}" data-tab="import">
        <span class="tab-icon">📤</span>
        <span class="tab-text">导入真题</span>
      </button>
    </div>
    <div class="exam-tab-content" id="exam-tab-content">
      <!-- 内容区域 -->
    </div>
  `

  // 绑定Tab点击事件
  container.querySelectorAll('.exam-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const tabName = tab.dataset.tab
      switchTab(tabName)
    })
  })
}

/**
 * 切换Tab
 */
async function switchTab(tabName) {
  currentTab = tabName

  // 更新Tab样式
  document.querySelectorAll('.exam-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === tabName)
  })

  const content = document.getElementById('exam-tab-content')
  if (!content) return

  // 清空并根据Tab加载内容
  switch (tabName) {
    case 'ai':
      renderAIGenerateTab(content)
      break
    case 'manual':
      await renderManualSelectTab(content)
      break
    case 'import':
      renderImportTab(content)
      break
  }
}

/**
 * 渲染AI生成题目Tab
 */
function renderAIGenerateTab(container) {
  container.innerHTML = `
    <div class="ai-generate-section">
      <div class="panel">
        <div class="panel-header">
          <h3 class="panel-title">AI智能出题</h3>
        </div>
        <div class="panel-body">
          <form id="question-generate-form">
            <div class="form-group">
              <label>知识点</label>
              <input type="text" id="qg-knowledge-points" placeholder="如：氧化还原反应,电化学" style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:6px;font-size:0.875rem;">
            </div>
            <div class="form-group">
              <label>难度</label>
              <select id="qg-difficulty" style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:6px;font-size:0.875rem;">
                <option value="easy">简单</option>
                <option value="medium" selected>中等</option>
                <option value="hard">困难</option>
              </select>
            </div>
            <div class="form-group">
              <label>题目数量</label>
              <input type="number" id="qg-quantity" value="10" min="1" max="50" style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:6px;font-size:0.875rem;">
            </div>
            <div class="form-group">
              <label>考试类型</label>
              <select id="qg-exam-type" style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:6px;font-size:0.875rem;">
                <option value="单元练习">单元练习</option>
                <option value="月考">月考</option>
                <option value="期中考试">期中考试</option>
                <option value="期末考试">期末考试</option>
              </select>
            </div>
            <button type="button" class="btn-primary" onclick="teacherModule.generateQuestionsFromTab()" style="width:100%;margin-top:8px;">
              开始生成
            </button>
          </form>
        </div>
      </div>
    </div>
  `
}

/**
 * 从Tab中获取参数并生成题目
 */
export async function generateQuestionsFromTab() {
  const knowledgePoints = document.getElementById('qg-knowledge-points').value.split(',').map(s => s.trim()).filter(s => s)
  const difficulty = document.getElementById('qg-difficulty').value
  const quantity = parseInt(document.getElementById('qg-quantity').value)
  const examType = document.getElementById('qg-exam-type').value

  if (!knowledgePoints.length) {
    Toast.error('请输入知识点')
    return
  }

  // 显示 Hermes Agent 流式界面
  showHermesThinking({
    task: TaskType.GENERATE_QUESTIONS,
    message: '正在生成题目...',
    onCancel: () => {
      hermesService.cancel()
      Toast.info('已取消生成')
    }
  })

  try {
    const result = await runQuestionGeneration({
      knowledge_points: knowledgePoints,
      difficulty,
      quantity,
      exam_type: examType
    })

    hideHermesThinking()

    if (result.success) {
      Toast.success(`成功生成 ${result.data.length} 道题目`)
      if (result.data.length > 0) {
        showGenerateResult(result.data)
      }
    } else {
      Toast.error(result.message || '生成失败')
    }
  } catch (error) {
    hideHermesThinking()
    Toast.error('生成失败：' + error.message)
  }
}

/**
 * 使用 Hermes Agent 执行题目生成（流式）
 */
async function runQuestionGeneration(params) {
  return new Promise((resolve, reject) => {
    let hasReturned = false
    let generatedQuestions = []

    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking:', event.content)
      window.updateHermesThinking?.({
        type: 'thinking',
        content: event.content
      })
    })

    hermesService.on('tool_started', (event) => {
      console.log('Hermes tool started:', event.tool, event.label)
      window.updateHermesThinking?.({
        type: 'tool_started',
        tool: event.tool,
        label: event.label
      })
    })

    hermesService.on('tool_call', (event) => {
      console.log('Hermes tool call:', event.tool, event.params)
      window.updateHermesThinking?.({
        type: 'tool_call',
        tool: event.tool,
        params: event.params
      })
    })

    hermesService.on('tool_result', (event) => {
      console.log('Hermes tool result:', event.result)
      if (event.result?.questions) {
        generatedQuestions = [...generatedQuestions, ...event.result.questions]
      }
      window.updateHermesThinking?.({
        type: 'tool_result',
        result: event.result
      })
    })

    hermesService.on('tool_completed', (event) => {
      console.log('Hermes tool completed:', event.tool, event.duration)
      window.updateHermesThinking?.({
        type: 'tool_completed',
        tool: event.tool,
        duration: event.duration
      })
    })

    hermesService.on('needs_confirmation', (event) => {
      console.log('Hermes needs confirmation:', event)
      if (event.confirmType === 'question_audit' && event.data) {
        showGenerateResult(event.data.questions || [])
      }
    })

    hermesService.on('final', (event) => {
      if (!hasReturned) {
        hasReturned = true
        const questions = event.result?.questions || generatedQuestions
        window.updateHermesThinking?.({
          type: 'final',
          result: { questions }
        })
        resolve({
          success: true,
          data: questions
        })
      }
    })

    hermesService.on('error', (event) => {
      if (!hasReturned) {
        hasReturned = true
        window.updateHermesThinking?.({
          type: 'error',
          content: event.error || event.message || 'Agent执行失败'
        })
        reject(new Error(event.error || event.message || 'Agent执行失败'))
      }
    })

    const streamResult = hermesService.executeStream(TaskType.GENERATE_QUESTIONS, params)

    if (!streamResult.success) {
      reject(new Error(streamResult.error || 'Agent启动失败'))
      return
    }

    hermesService.processStream(streamResult.reader, (event) => {
      // 事件会在回调中处理
    }).catch((error) => {
      if (!hasReturned) {
        hasReturned = true
        reject(error)
      }
    })
  })
}

/**
 * 渲染手动选题Tab（三栏布局）
 */
async function renderManualSelectTab(container) {
  container.innerHTML = `
    <div class="manual-select-layout">
      <!-- 左栏：筛选条件 -->
      <div class="filter-panel">
        <h4 class="filter-title">筛选条件</h4>
        <div class="filter-group">
          <label>来源</label>
          <select id="filter-region" onchange="teacherModule.applyFilter()">
            <option value="all">全部</option>
            <option value="长沙">长沙市</option>
            <option value="北京">北京市</option>
            <option value="上海">上海市</option>
            <option value="广州">广州市</option>
            <option value="深圳">深圳市</option>
          </select>
        </div>
        <div class="filter-group">
          <label>年份</label>
          <select id="filter-year" onchange="teacherModule.applyFilter()">
            <option value="all">全部</option>
            <option value="2024">2024年</option>
            <option value="2023">2023年</option>
            <option value="2022">2022年</option>
            <option value="2021">2021年</option>
          </select>
        </div>
        <div class="filter-group">
          <label>知识点</label>
          <select id="filter-knowledge" onchange="teacherModule.applyFilter()">
            <option value="all">全部</option>
            <option value="氧化还原反应">氧化还原反应</option>
            <option value="离子反应">离子反应</option>
            <option value="电化学">电化学</option>
            <option value="化学平衡">化学平衡</option>
            <option value="电解质">电解质</option>
          </select>
        </div>
        <div class="filter-group">
          <label>难度</label>
          <div class="difficulty-options">
            <label class="radio-label">
              <input type="radio" name="difficulty" value="all" checked onchange="teacherModule.applyFilter()"> 全部
            </label>
            <label class="radio-label">
              <input type="radio" name="difficulty" value="easy" onchange="teacherModule.applyFilter()"> 基础
            </label>
            <label class="radio-label">
              <input type="radio" name="difficulty" value="medium" onchange="teacherModule.applyFilter()"> 中等
            </label>
            <label class="radio-label">
              <input type="radio" name="difficulty" value="hard" onchange="teacherModule.applyFilter()"> 困难
            </label>
          </div>
        </div>
        <button class="btn-secondary btn-sm" onclick="teacherModule.loadHistoricalQuestions()" style="width:100%;margin-top:12px;">
          重置筛选
        </button>
      </div>

      <!-- 中栏：真题列表 -->
      <div class="questions-list-panel">
        <div class="list-header">
          <h4 class="list-title">历年真题</h4>
          <span class="list-count" id="questions-count">共 0 题</span>
        </div>
        <div class="questions-list" id="historical-questions-list">
          <div class="empty-state">
            <div class="empty-state-icon">📋</div>
            <p>正在加载真题...</p>
          </div>
        </div>
      </div>

      <!-- 右栏：已选题目 -->
      <div class="selected-panel">
        <div class="selected-header">
          <h4 class="selected-title">已选题目</h4>
          <span class="selected-count" id="selected-count">共 0 题</span>
        </div>
        <div class="selected-list" id="selected-questions-list">
          <div class="empty-state">
            <div class="empty-state-icon">📝</div>
            <p>点击真题添加到右侧</p>
          </div>
        </div>
        <div class="selected-actions">
          <button class="btn-secondary btn-sm" onclick="teacherModule.clearSelectedQuestions()">清空</button>
          <button class="btn-primary btn-sm" onclick="teacherModule.addSelectedToExam()">加入试卷</button>
        </div>
      </div>
    </div>
  `

  // 加载历史真题
  await loadHistoricalQuestions()
}

/**
 * 加载历史真题（通过 Hermes Agent）
 */
export async function loadHistoricalQuestions() {
  const listContainer = document.getElementById('historical-questions-list')
  if (!listContainer) return

  // 获取筛选条件
  const region = document.getElementById('filter-region')?.value || 'all'
  const year = document.getElementById('filter-year')?.value || 'all'
  const knowledgePoint = document.getElementById('filter-knowledge')?.value || 'all'
  const difficultyRadio = document.querySelector('input[name="difficulty"]:checked')
  const difficulty = difficultyRadio ? difficultyRadio.value : 'all'

  // 构建请求参数
  const params = {}
  if (region !== 'all') params.region = region
  if (year !== 'all') params.year = year
  if (knowledgePoint !== 'all') params.knowledge_point = knowledgePoint
  if (difficulty !== 'all') params.difficulty = difficulty

  showLoading('加载真题...')

  try {
    // 通过 Hermes Agent 检索历年真题
    const result = await runSearchHistorical(params)

    hideLoading()

    if (result.success) {
      historicalQuestions = result.data || []
      renderHistoricalQuestions(historicalQuestions)
    } else {
      Toast.error(result.message || '加载真题失败')
      listContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">❌</div>
          <p>加载失败</p>
          <button class="btn-secondary btn-sm" onclick="teacherModule.loadHistoricalQuestions()">重试</button>
        </div>
      `
    }
  } catch (error) {
    hideLoading()
    Toast.error('加载失败：' + error.message)
    listContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">❌</div>
        <p>加载失败</p>
        <button class="btn-secondary btn-sm" onclick="teacherModule.loadHistoricalQuestions()">重试</button>
      </div>
    `
  }
}

/**
 * 通过 Hermes Agent 执行历年真题检索
 */
async function runSearchHistorical(params) {
  return new Promise((resolve, reject) => {
    let hasReturned = false
    let searchResults = []

    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking:', event.content)
      window.updateHermesThinking?.({
        type: 'thinking',
        content: event.content
      })
    })

    hermesService.on('tool_started', (event) => {
      console.log('Hermes tool started:', event.tool, event.label)
      window.updateHermesThinking?.({
        type: 'tool_started',
        tool: event.tool,
        label: event.label
      })
    })

    hermesService.on('tool_call', (event) => {
      console.log('Hermes tool call:', event.tool, event.params)
      window.updateHermesThinking?.({
        type: 'tool_call',
        tool: event.tool,
        params: event.params
      })
    })

    hermesService.on('tool_result', (event) => {
      console.log('Hermes tool result:', event.result)
      if (event.result) {
        // exam_search_historical 返回格式: { questions: [...], total: N }
        if (event.result.questions) {
          searchResults = [...searchResults, ...event.result.questions]
        } else if (Array.isArray(event.result)) {
          searchResults = [...searchResults, ...event.result]
        }
      }
      window.updateHermesThinking?.({
        type: 'tool_result',
        result: event.result
      })
    })

    hermesService.on('tool_completed', (event) => {
      console.log('Hermes tool completed:', event.tool, event.duration)
      window.updateHermesThinking?.({
        type: 'tool_completed',
        tool: event.tool,
        duration: event.duration
      })
    })

    hermesService.on('final', (event) => {
      if (!hasReturned) {
        hasReturned = true
        // 从最终结果中提取题目
        let finalQuestions = []
        if (event.result?.questions) {
          finalQuestions = event.result.questions
        } else if (event.result?.data) {
          finalQuestions = event.result.data
        } else if (Array.isArray(event.result)) {
          finalQuestions = event.result
        }
        window.updateHermesThinking?.({
          type: 'final',
          result: { questions: finalQuestions.length > 0 ? finalQuestions : searchResults }
        })
        resolve({
          success: true,
          data: finalQuestions.length > 0 ? finalQuestions : searchResults
        })
      }
    })

    hermesService.on('error', (event) => {
      if (!hasReturned) {
        hasReturned = true
        window.updateHermesThinking?.({
          type: 'error',
          content: event.error || event.message || 'Agent执行失败'
        })
        reject(new Error(event.error || event.message || 'Agent执行失败'))
      }
    })

    const streamResult = hermesService.executeStream(TaskType.SEARCH_HISTORICAL, params)

    if (!streamResult.success) {
      reject(new Error(streamResult.error || 'Agent启动失败'))
      return
    }

    hermesService.processStream(streamResult.reader, (event) => {
      // 事件会在回调中处理
    }).catch((error) => {
      if (!hasReturned) {
        hasReturned = true
        reject(error)
      }
    })
  })
}

/**
 * 应用筛选
 */
export function applyFilter() {
  loadHistoricalQuestions()
}

/**
 * 渲染历史真题列表
 */
function renderHistoricalQuestions(questions) {
  const listContainer = document.getElementById('historical-questions-list')
  const countEl = document.getElementById('questions-count')
  if (!listContainer) return

  if (countEl) countEl.textContent = `共 ${questions.length} 题`

  if (questions.length === 0) {
    listContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📭</div>
        <p>暂无符合条件的真题</p>
      </div>
    `
    return
  }

  listContainer.innerHTML = questions.map(q => `
    <div class="question-item" data-id="${q.id || q._id}">
      <div class="question-item-header">
        <span class="question-source">${q.source || q.region || '未知来源'}</span>
        <span class="question-year">${q.year || ''}</span>
      </div>
      <div class="question-item-content">${q.content || q.title || '题目内容'}</div>
      <div class="question-item-meta">
        <span class="question-kp">${(q.knowledge_points || q.knowledge || []).slice(0, 2).join(', ')}</span>
        <span class="question-difficulty difficulty-${q.difficulty}">${getDifficultyName(q.difficulty)}</span>
      </div>
      <button class="btn-add-question" onclick="teacherModule.addQuestionToSelected('${q.id || q._id}')">
        + 添加
      </button>
    </div>
  `).join('')
}

/**
 * 添加题目到已选列表
 */
export function addQuestionToSelected(questionId) {
  const question = historicalQuestions.find(q => (q.id || q._id) === questionId)
  if (!question) return

  // 检查是否已选
  if (selectedQuestions.some(q => (q.id || q._id) === questionId)) {
    Toast.info('该题目已在选择列表中')
    return
  }

  selectedQuestions.push(question)
  renderSelectedQuestions()
  Toast.success('已添加题目')
}

/**
 * 从已选列表移除题目
 */
export function removeQuestionFromSelected(questionId) {
  selectedQuestions = selectedQuestions.filter(q => (q.id || q._id) !== questionId)
  renderSelectedQuestions()
}

/**
 * 清空已选题目
 */
export function clearSelectedQuestions() {
  if (selectedQuestions.length === 0) return
  if (!confirm('确定要清空已选的题目吗？')) return
  selectedQuestions = []
  renderSelectedQuestions()
  Toast.info('已清空')
}

/**
 * 渲染已选题目列表
 */
function renderSelectedQuestions() {
  const listContainer = document.getElementById('selected-questions-list')
  const countEl = document.getElementById('selected-count')
  if (!listContainer) return

  if (countEl) countEl.textContent = `共 ${selectedQuestions.length} 题`

  if (selectedQuestions.length === 0) {
    listContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📝</div>
        <p>点击真题添加到右侧</p>
      </div>
    `
    return
  }

  listContainer.innerHTML = selectedQuestions.map((q, index) => `
    <div class="selected-item">
      <div class="selected-item-number">${index + 1}</div>
      <div class="selected-item-content">${q.content || q.title || '题目内容'}</div>
      <button class="btn-remove" onclick="teacherModule.removeQuestionFromSelected('${q.id || q._id}')">×</button>
    </div>
  `).join('')
}

/**
 * 将选中的题目加入试卷
 */
export async function addSelectedToExam() {
  if (selectedQuestions.length === 0) {
    Toast.error('请先选择题目')
    return
  }

  // 显示创建考试弹窗，让用户输入考试信息
  showCreateExamModalWithQuestions(selectedQuestions)
}

/**
 * 显示创建考试弹窗（带预选题目）
 */
export function showCreateExamModalWithQuestions(questions) {
  const modal = document.getElementById('exam-modal')
  if (!modal) return

  currentExam = null
  selectedQuestions = questions // 保存引用
  document.getElementById('exam-form').reset()

  // 更新弹窗标题
  const titleEl = modal.querySelector('.modal-title')
  if (titleEl) titleEl.textContent = '创建考试（已选题目）'

  modal.style.display = 'flex'
}

/**
 * 渲染导入真题Tab
 */
function renderImportTab(container) {
  // 重置导入状态
  resetImportState()

  container.innerHTML = `
    <div class="import-section">
      <!-- Step 1: 选择文件 -->
      <div class="import-step" id="import-step-1">
        <div class="step-header">
          <span class="step-number">1</span>
          <span class="step-title">选择文件</span>
        </div>
        <div class="step-content">
          <div class="upload-zone" id="import-upload-zone">
            <input type="file" id="import-file-input" accept=".pdf,.docx,.pptx,.jpg,.jpeg,.png,.gif,.bmp" style="display:none;">
            <div class="upload-icon">
              <svg viewBox="0 0 24 24" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </div>
            <h3>点击或拖拽上传文件</h3>
            <p>支持 PDF、DOCX、PPTX、JPG、PNG 等格式</p>
            <p style="margin-top:8px;font-size:0.75rem;color:var(--text-muted);">
              系统将自动选择最佳解析方式：PDF/DOCX/PPTX 使用 MinerU，图片使用 OCR+视觉模型
            </p>
          </div>
        </div>
      </div>

      <!-- Step 2: 解析中 -->
      <div class="import-step" id="import-step-2" style="display:none;">
        <div class="step-header">
          <span class="step-number">2</span>
          <span class="step-title">智能解析中</span>
        </div>
        <div class="step-content">
          <div class="parsing-status">
            <div class="parsing-icon">🔄</div>
            <div class="parsing-message" id="parsing-message">正在上传文件...</div>
            <div class="parsing-method" id="parsing-method"></div>
          </div>
        </div>
      </div>

      <!-- Step 3: 解析结果预览 -->
      <div class="import-step" id="import-step-3" style="display:none;">
        <div class="step-header">
          <span class="step-number">3</span>
          <span class="step-title">解析结果预览</span>
        </div>
        <div class="step-content">
          <div class="parse-preview" id="parse-preview"></div>
          <div class="step-actions">
            <button class="btn-secondary" onclick="teacherModule.resetImport()">重新选择</button>
            <button class="btn-primary" onclick="teacherModule.goToStep(4)">下一步</button>
          </div>
        </div>
      </div>

      <!-- Step 4: 选择目标真题集 -->
      <div class="import-step" id="import-step-4" style="display:none;">
        <div class="step-header">
          <span class="step-number">4</span>
          <span class="step-title">选择目标真题集</span>
        </div>
        <div class="step-content">
          <div class="exam-sets-selector" id="exam-sets-selector">
            <div class="loading-state">加载真题集列表...</div>
          </div>
          <div class="step-actions">
            <button class="btn-secondary" onclick="teacherModule.goToStep(3)">上一步</button>
            <button class="btn-primary" id="btn-confirm-import" onclick="teacherModule.confirmImport()" disabled>确认导入</button>
          </div>
        </div>
      </div>

      <!-- Step 5: 确认导入 -->
      <div class="import-step" id="import-step-5" style="display:none;">
        <div class="step-header">
          <span class="step-number">5</span>
          <span class="step-title">导入完成</span>
        </div>
        <div class="step-content">
          <div class="import-success">
            <div class="success-icon">✅</div>
            <div class="success-message" id="import-success-message">导入成功！</div>
          </div>
          <div class="step-actions">
            <button class="btn-primary" onclick="teacherModule.resetImport()">继续导入</button>
            <button class="btn-secondary" onclick="teacherModule.goToManualTab()">查看真题</button>
          </div>
        </div>
      </div>
    </div>
  `

  // 初始化上传功能
  initImportUpload()
}

/**
 * 重置导入状态
 */
function resetImportState() {
  importState = {
    step: 1,
    fileData: null,
    parsedResult: null,
    targetSetId: null
  }
}

/**
 * 初始化导入上传功能
 */
function initImportUpload() {
  const uploadZone = document.getElementById('import-upload-zone')
  const fileInput = document.getElementById('import-file-input')

  if (uploadZone && fileInput) {
    uploadZone.addEventListener('click', () => fileInput.click())
    fileInput.addEventListener('change', handleImportFileSelect)

    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault()
      uploadZone.classList.add('dragover')
    })

    uploadZone.addEventListener('dragleave', () => {
      uploadZone.classList.remove('dragover')
    })

    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault()
      uploadZone.classList.remove('dragover')
      if (e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files
        handleImportFileSelect({ target: fileInput })
      }
    })
  }
}

/**
 * 处理导入文件选择
 */
async function handleImportFileSelect(e) {
  const fileInput = e.target
  if (fileInput.files.length === 0) return

  const file = fileInput.files[0]

  // 验证文件类型
  const allowedTypes = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/bmp'
  ]

  // 检查文件扩展名
  const ext = file.name.split('.').pop().toLowerCase()
  const allowedExts = ['pdf', 'docx', 'pptx', 'jpg', 'jpeg', 'png', 'gif', 'bmp']

  if (!allowedExts.includes(ext)) {
    Toast.error('不支持的文件格式')
    return
  }

  // 读取文件
  try {
    const fileData = await readFileAsBase64(file)
    importState.fileData = fileData

    // 确定文件类型
    let fileType = 'auto'
    if (ext === 'pdf') fileType = 'pdf'
    else if (['docx', 'pptx'].includes(ext)) fileType = 'document'
    else if (['jpg', 'jpeg', 'png', 'gif', 'bmp'].includes(ext)) fileType = 'image'

    // 开始解析
    await startParsing(fileType)
  } catch (error) {
    Toast.error('读取文件失败：' + error.message)
  }

  // 清空文件输入
  fileInput.value = ''
}

/**
 * 开始解析文件（通过 Hermes Agent）
 */
async function startParsing(fileType) {
  goToStep(2)

  // 更新解析状态
  const parsingMessage = document.getElementById('parsing-message')
  const parsingMethod = document.getElementById('parsing-method')

  if (parsingMessage) parsingMessage.textContent = '正在上传文件...'
  if (parsingMethod) parsingMethod.textContent = ''

  try {
    // 通过 Hermes Agent 执行智能文档解析
    const result = await runSmartParseWithHermes(importState.fileData, fileType)

    if (result.success) {
      importState.parsedResult = result.data

      // 更新状态显示
      if (parsingMessage) parsingMessage.textContent = '解析完成！'
      if (parsingMethod && result.data.method) {
        parsingMethod.textContent = `解析方式：${result.data.method}`
      }

      // 延迟一下显示预览
      setTimeout(() => {
        goToStep(3)
        renderParsePreview(result.data)
      }, 1000)
    } else {
      Toast.error(result.message || '解析失败')
      goToStep(1)
    }
  } catch (error) {
    Toast.error('解析失败：' + error.message)
    goToStep(1)
  }
}

/**
 * 通过 Hermes Agent 执行智能文档解析
 */
async function runSmartParseWithHermes(fileData, fileType) {
  return new Promise((resolve, reject) => {
    let hasReturned = false
    let parseResult = null

    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking:', event.content)
      window.updateHermesThinking?.({
        type: 'thinking',
        content: event.content
      })
    })

    hermesService.on('tool_started', (event) => {
      console.log('Hermes tool started:', event.tool, event.label)
      window.updateHermesThinking?.({
        type: 'tool_started',
        tool: event.tool,
        label: event.label
      })
      // 同时更新解析状态 UI
      const parsingMessage = document.getElementById('parsing-message')
      const parsingMethod = document.getElementById('parsing-method')
      if (parsingMessage) {
        parsingMessage.textContent = `正在${event.label || '解析'}...`
      }
      if (parsingMethod && event.tool) {
        parsingMethod.textContent = `使用工具：${event.tool}`
      }
    })

    hermesService.on('tool_call', (event) => {
      console.log('Hermes tool call:', event.tool, event.params)
      window.updateHermesThinking?.({
        type: 'tool_call',
        tool: event.tool,
        params: event.params
      })
    })

    hermesService.on('tool_result', (event) => {
      console.log('Hermes tool result:', event.result)
      if (event.result) {
        parseResult = event.result
      }
      window.updateHermesThinking?.({
        type: 'tool_result',
        result: event.result
      })
    })

    hermesService.on('tool_completed', (event) => {
      console.log('Hermes tool completed:', event.tool, event.duration)
      window.updateHermesThinking?.({
        type: 'tool_completed',
        tool: event.tool,
        duration: event.duration
      })
      // 同时更新解析状态 UI
      const parsingMessage = document.getElementById('parsing-message')
      if (parsingMessage) {
        parsingMessage.textContent = '解析完成！'
      }
    })

    hermesService.on('final', (event) => {
      if (!hasReturned) {
        hasReturned = true
        const resultData = event.result || parseResult || {}
        // 确保返回的数据格式正确
        let finalData = resultData
        if (!resultData.questions && resultData.data) {
          finalData = resultData.data
        }
        window.updateHermesThinking?.({
          type: 'final',
          result: finalData
        })
        resolve({
          success: true,
          data: finalData
        })
      }
    })

    hermesService.on('error', (event) => {
      if (!hasReturned) {
        hasReturned = true
        window.updateHermesThinking?.({
          type: 'error',
          content: event.error || event.message || 'Agent执行失败'
        })
        reject(new Error(event.error || event.message || 'Agent执行失败'))
      }
    })

    const streamResult = hermesService.executeStream(TaskType.IMPORT_QUESTIONS, {
      file_data: fileData,
      file_type: fileType,
      task: 'extract_questions'
    })

    if (!streamResult.success) {
      reject(new Error(streamResult.error || 'Agent启动失败'))
      return
    }

    hermesService.processStream(streamResult.reader, (event) => {
      // 事件会在回调中处理
    }).catch((error) => {
      if (!hasReturned) {
        hasReturned = true
        reject(error)
      }
    })
  })
}

/**
 * 渲染解析预览
 */
function renderParsePreview(data) {
  const container = document.getElementById('parse-preview')
  if (!container) return

  const questions = data.questions || []
  const rawText = data.raw_text || ''

  if (questions.length === 0 && !rawText) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">❌</div>
        <p>未能从文件中提取到题目</p>
        <p style="font-size:0.75rem;color:var(--text-muted);margin-top:8px;">请尝试手动输入或检查文件内容</p>
      </div>
    `
    return
  }

  container.innerHTML = `
    <div class="preview-summary">
      <span>共识别到 ${questions.length} 道题目</span>
    </div>
    <div class="preview-questions" id="preview-questions-list">
      ${questions.slice(0, 10).map((q, i) => `
        <div class="preview-question-item">
          <div class="preview-question-number">${i + 1}</div>
          <div class="preview-question-content">${q.content || q.title || '题目内容'}</div>
          <div class="preview-question-meta">
            ${(q.knowledge_points || []).slice(0, 2).join(', ')}
          </div>
        </div>
      `).join('')}
      ${questions.length > 10 ? `<div class="preview-more">还有 ${questions.length - 10} 道题目...</div>` : ''}
    </div>
    ${rawText ? `
      <div class="preview-raw-text">
        <h5>原始文本</h5>
        <pre>${rawText.substring(0, 500)}${rawText.length > 500 ? '...' : ''}</pre>
      </div>
    ` : ''}
  `
}

/**
 * 加载真题集列表
 */
async function loadExamSets() {
  const container = document.getElementById('exam-sets-selector')
  if (!container) return

  try {
    const result = await examService.getExamSets()

    if (result.success) {
      const sets = result.data || []

      if (sets.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📚</div>
            <p>暂无真题集</p>
            <button class="btn-primary btn-sm" onclick="teacherModule.showCreateExamSetModal()">创建真题集</button>
          </div>
        `
        return
      }

      container.innerHTML = `
        <div class="exam-sets-list">
          ${sets.map(set => `
            <div class="exam-set-item ${importState.targetSetId === set.id ? 'selected' : ''}" data-id="${set.id}" onclick="teacherModule.selectExamSet('${set.id}')">
              <div class="exam-set-name">${set.name}</div>
              <div class="exam-set-meta">
                <span>${set.question_count || 0} 题</span>
                <span>${set.source || ''} ${set.year || ''}</span>
              </div>
            </div>
          `).join('')}
        </div>
        <button class="btn-secondary btn-sm" onclick="teacherModule.showCreateExamSetModal()" style="margin-top:12px;">
          + 创建新真题集
        </button>
      `
    } else {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">❌</div>
          <p>加载失败</p>
          <button class="btn-secondary btn-sm" onclick="teacherModule.loadExamSets()">重试</button>
        </div>
      `
    }
  } catch (error) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">❌</div>
        <p>加载失败：${error.message}</p>
        <button class="btn-secondary btn-sm" onclick="teacherModule.loadExamSets()">重试</button>
      </div>
    `
  }
}

/**
 * 选择目标真题集
 */
export function selectExamSet(setId) {
  importState.targetSetId = setId

  // 更新UI
  document.querySelectorAll('.exam-set-item').forEach(item => {
    item.classList.toggle('selected', item.dataset.id === setId)
  })

  // 启用确认导入按钮
  const btn = document.getElementById('btn-confirm-import')
  if (btn) btn.disabled = false
}

/**
 * 显示创建真题集弹窗
 */
export function showCreateExamSetModal() {
  const modal = document.getElementById('create-exam-set-modal')
  if (!modal) {
    // 如果弹窗不存在，创建一个简单的prompt
    const name = prompt('请输入真题集名称：')
    if (name) {
      createExamSet(name)
    }
    return
  }

  modal.style.display = 'flex'
}

/**
 * 创建真题集
 */
async function createExamSet(name) {
  showLoading('创建真题集...')

  try {
    const result = await examService.createExamSet({ name })

    if (result.success) {
      Toast.success('创建成功')
      // 重新加载真题集列表
      await loadExamSets()
      // 自动选中新创建的真题集
      if (result.data && result.data.id) {
        selectExamSet(result.data.id)
      }
    } else {
      Toast.error(result.message || '创建失败')
    }
  } catch (error) {
    Toast.error('创建失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 确认导入
 */
export async function confirmImport() {
  if (!importState.targetSetId) {
    Toast.error('请选择目标真题集')
    return
  }

  if (!importState.parsedResult || !importState.parsedResult.questions) {
    Toast.error('没有可导入的题目')
    return
  }

  showLoading('导入中...')

  try {
    const questions = importState.parsedResult.questions
    const result = await examService.importQuestions(importState.targetSetId, questions)

    if (result.success) {
      goToStep(5)
      const messageEl = document.getElementById('import-success-message')
      if (messageEl) {
        messageEl.textContent = `成功导入 ${questions.length} 道题目到真题集！`
      }
    } else {
      Toast.error(result.message || '导入失败')
    }
  } catch (error) {
    Toast.error('导入失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 切换到指定步骤
 */
export function goToStep(step) {
  importState.step = step

  // 隐藏所有步骤
  for (let i = 1; i <= 5; i++) {
    const stepEl = document.getElementById(`import-step-${i}`)
    if (stepEl) stepEl.style.display = 'none'
  }

  // 显示当前步骤
  const currentStepEl = document.getElementById(`import-step-${step}`)
  if (currentStepEl) currentStepEl.style.display = 'block'

  // 如果是步骤4，加载真题集列表
  if (step === 4) {
    loadExamSets()
  }
}

/**
 * 切换到手动选题Tab
 */
export function goToManualTab() {
  switchTab('manual')
}

/**
 * 读取文件为Base64
 */
function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(e.target.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/**
 * 显示生成结果弹窗
 */
function showGenerateResult(questions) {
  const modal = document.getElementById('question-result-modal')
  if (!modal) return

  const container = document.getElementById('question-result-list')
  if (container) {
    container.innerHTML = questions.map(q => `
      <div class="result-question">
        <div class="question-type">${getQuestionTypeName(q.type)}</div>
        <div class="question-content">${q.content || q.title}</div>
        <div class="question-answer">正确答案: ${q.correct_answer}</div>
        ${q.knowledge_points?.length ? `<div class="question-kps">知识点: ${q.knowledge_points.join(', ')}</div>` : ''}
      </div>
    `).join('')
  }

  modal.style.display = 'flex'
}

/**
 * 获取题目类型名称
 */
function getQuestionTypeName(type) {
  const names = {
    choice: '选择题',
    fill_blank: '填空题',
    judgment: '判断题',
    short_answer: '简答题',
    calculation: '计算题'
  }
  return names[type] || type || '选择题'
}

/**
 * 获取难度名称
 */
function getDifficultyName(difficulty) {
  const names = {
    easy: '基础',
    medium: '中等',
    hard: '困难'
  }
  return names[difficulty] || difficulty || '中等'
}

/**
 * 关闭生成弹窗
 */
export function closeGenerateModal() {
  const modal = document.getElementById('question-generate-modal')
  if (modal) modal.style.display = 'none'
}

/**
 * 关闭结果弹窗
 */
export function closeResultModal() {
  const modal = document.getElementById('question-result-modal')
  if (modal) modal.style.display = 'none'
}

/**
 * 关闭详情弹窗
 */
export function closeQuestionDetailModal() {
  const modal = document.getElementById('question-detail-modal')
  if (modal) modal.style.display = 'none'
}

// ==================== 原有考试CRUD功能 ====================

/**
 * 加载考试列表（原有功能）
 */
export async function loadExamList() {
  const container = document.getElementById('exam-list')
  if (!container) return

  showLoading('加载考试列表...')

  try {
    const result = await examService.getExamList()

    if (result.success) {
      currentExamList = result.data || []
      renderExamList(currentExamList)
    } else {
      Toast.error('加载考试列表失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 渲染考试列表（原有功能）
 */
function renderExamList(exams) {
  const container = document.getElementById('exam-list')
  if (!container) return

  if (exams.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-size:3rem;margin-bottom:16px;">📝</div>
        <p>暂无考试</p>
        <button class="btn-primary" onclick="showCreateExamModal()">创建新考试</button>
      </div>
    `
    return
  }

  // 这里需要包装成Tab结构
  const tabContent = container.querySelector('.exam-tab-content') || container
  if (tabContent.id !== 'exam-tab-content') {
    container.innerHTML = `
      <div class="exam-tabs">
        <button class="exam-tab" data-tab="ai">📝 AI生成题目</button>
        <button class="exam-tab" data-tab="manual">📚 手动选题</button>
        <button class="exam-tab" data-tab="import">📤 导入真题</button>
      </div>
      <div class="exam-tab-content" id="exam-tab-content">
        <div class="exam-list-wrapper">
          ${exams.map(exam => `
            <div class="exam-card" data-id="${exam.id}">
              <div class="exam-header">
                <h3>${exam.title}</h3>
                <span class="exam-status status-${exam.status}">${getExamStatusText(exam.status)}</span>
              </div>
              <div class="exam-info">
                <span>题目数量：${exam.question_count || 0}</span>
                <span>总分：${exam.total_score || 0}</span>
                <span>时长：${exam.duration || 0}分钟</span>
              </div>
              <div class="exam-actions">
                <button class="btn-secondary" onclick="viewExamDetail('${exam.id}')">查看</button>
                <button class="btn-secondary" onclick="editExam('${exam.id}')">编辑</button>
                <button class="btn-danger" onclick="deleteExam('${exam.id}')">删除</button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `
  }
}

/**
 * 获取考试状态文本
 */
function getExamStatusText(status) {
  const statusMap = {
    draft: '草稿',
    published: '已发布',
    ongoing: '进行中',
    ended: '已结束'
  }
  return statusMap[status] || status
}

/**
 * 显示创建考试弹窗
 */
export function showCreateExamModal() {
  const modal = document.getElementById('exam-modal')
  if (!modal) return

  currentExam = null
  const form = document.getElementById('exam-form')
  if (form) form.reset()

  const titleEl = modal.querySelector('.modal-title')
  if (titleEl) titleEl.textContent = '创建考试'

  modal.style.display = 'flex'
}

/**
 * 编辑考试
 */
export async function editExam(examId) {
  showLoading()

  try {
    const result = await examService.getExamDetail(examId)

    if (result.success) {
      currentExam = result.data
      populateExamForm(currentExam)
      showCreateExamModal()
    } else {
      Toast.error('获取考试详情失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 填充考试表单
 */
function populateExamForm(exam) {
  const titleEl = document.getElementById('exam-title')
  const descEl = document.getElementById('exam-description')
  const durationEl = document.getElementById('exam-duration')
  const scoreEl = document.getElementById('exam-total-score')

  if (titleEl) titleEl.value = exam.title || ''
  if (descEl) descEl.value = exam.description || ''
  if (durationEl) durationEl.value = exam.duration || 60
  if (scoreEl) scoreEl.value = exam.total_score || 100
}

/**
 * 保存考试
 */
export async function saveExam(examData) {
  showLoading()

  try {
    let result

    if (currentExam && currentExam.id) {
      result = await examService.updateExam(currentExam.id, examData)
    } else {
      result = await examService.createExam(examData)
    }

    if (result.success) {
      Toast.success('保存成功')
      closeExamModal()
      await loadExamList()
    } else {
      Toast.error(result.message || '保存失败')
    }
  } catch (error) {
    Toast.error('保存失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 删除考试
 */
export async function deleteExam(examId) {
  if (!confirm('确定要删除这个考试吗？')) return

  showLoading()

  try {
    const result = await examService.deleteExam(examId)

    if (result.success) {
      Toast.success('删除成功')
      await loadExamList()
    } else {
      Toast.error(result.message || '删除失败')
    }
  } catch (error) {
    Toast.error('删除失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 查看考试详情
 */
export async function viewExamDetail(examId) {
  showLoading()

  try {
    const result = await examService.getExamDetail(examId)

    if (result.success) {
      currentExam = result.data
      renderExamDetail(result.data)
    } else {
      Toast.error('获取详情失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 渲染考试详情
 */
function renderExamDetail(exam) {
  const modal = document.getElementById('exam-detail-modal')
  if (!modal) return

  const content = document.getElementById('exam-detail-content')
  if (!content) return

  content.innerHTML = `
    <h2>${exam.title}</h2>
    <div class="detail-info">
      <p><strong>描述：</strong>${exam.description || '无'}</p>
      <p><strong>时长：</strong>${exam.duration}分钟</p>
      <p><strong>总分：</strong>${exam.total_score}</p>
      <p><strong>状态：</strong>${getExamStatusText(exam.status)}</p>
    </div>
    <div class="detail-questions">
      <h3>题目列表</h3>
      ${renderQuestionList(exam.questions || [])}
    </div>
  `

  modal.style.display = 'flex'
}

/**
 * 渲染题目列表
 */
function renderQuestionList(questions) {
  if (questions.length === 0) {
    return '<p class="empty">暂无题目</p>'
  }

  return questions.map((q, i) => `
    <div class="question-item">
      <span class="question-number">${i + 1}</span>
      <span class="question-content">${q.content || q.title}</span>
      <span class="question-score">${q.score}分</span>
    </div>
  `).join('')
}

/**
 * 关闭考试弹窗
 */
export function closeExamModal() {
  const modal = document.getElementById('exam-modal')
  if (modal) modal.style.display = 'none'
}

/**
 * 关闭详情弹窗
 */
export function closeExamDetailModal() {
  const modal = document.getElementById('exam-detail-modal')
  if (modal) modal.style.display = 'none'
}

// 导出全局函数
if (typeof window !== 'undefined') {
  // Tab相关
  window.switchTab = switchTab
  window.teacherModule = window.teacherModule || {}

  // AI生成
  window.teacherModule.generateQuestionsFromTab = generateQuestionsFromTab

  // 手动选题
  window.teacherModule.applyFilter = applyFilter
  window.teacherModule.loadHistoricalQuestions = loadHistoricalQuestions
  window.teacherModule.addQuestionToSelected = addQuestionToSelected
  window.teacherModule.removeQuestionFromSelected = removeQuestionFromSelected
  window.teacherModule.clearSelectedQuestions = clearSelectedQuestions
  window.teacherModule.addSelectedToExam = addSelectedToExam
  window.teacherModule.showCreateExamModalWithQuestions = showCreateExamModalWithQuestions

  // 导入真题
  window.teacherModule.resetImport = () => { resetImportState(); renderImportTab(document.getElementById('exam-tab-content')) }
  window.teacherModule.goToStep = goToStep
  window.teacherModule.selectExamSet = selectExamSet
  window.teacherModule.showCreateExamSetModal = showCreateExamSetModal
  window.teacherModule.confirmImport = confirmImport
  window.teacherModule.goToManualTab = goToManualTab

  // 原有考试CRUD
  window.showCreateExamModal = showCreateExamModal
  window.editExam = editExam
  window.deleteExam = deleteExam
  window.viewExamDetail = viewExamDetail
  window.closeExamModal = closeExamModal
  window.closeExamDetailModal = closeExamDetailModal
  window.saveExam = saveExam
  window.closeGenerateModal = closeGenerateModal
  window.closeResultModal = closeResultModal
  window.closeQuestionDetailModal = closeQuestionDetailModal

  // 原有初始化
  window.teacherModule.initExamModule = initExamModule
  window.teacherModule.loadExamList = loadExamList
}
