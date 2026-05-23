/**
 * 教师端 - OCR答题卡模块
 * 包含答题卡识别和服务状态两大功能
 */
import { api } from '../../services/api.js'
import { examService, userService, classService } from '../../services/index.js'
import { hermesService, TaskType } from '../../services/hermes.js'
import { Toast, showHermesThinking, hideHermesThinking, showLoading, hideLoading } from '../../components/index.js'

// 全局状态
let currentOcrImageData = null
let currentOcrPreview = null
let currentOcrAnswers = {}
let currentOcrStudentId = null  // 确认后的学生学号
let currentOcrStudentName = null  // 确认后的学生姓名
let currentOcrTab = 'recognize' // 当前Tab: recognize, status

// 服务状态缓存
let servicesStatus = null
let lastStatusCheck = null

/**
 * 初始化OCR上传功能
 */
export function initOcrUpload() {
  const uploadZone = document.getElementById('upload-zone')
  const fileInput = document.getElementById('file-input')

  if (uploadZone && fileInput) {
    uploadZone.addEventListener('click', () => fileInput.click())
    fileInput.addEventListener('change', handleFileSelect)

    // 拖拽上传
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
        handleFileSelect({ target: fileInput })
      }
    })
  }

  // 初始化OCR Tab容器
  initOcrTabs()

  // 初始化班级选择下拉框
  initOcrClassSelect()
}

/**
 * 初始化OCR Tab
 */
function initOcrTabs() {
  const container = document.getElementById('ocr-tabs-container')
  if (!container) {
    // 如果没有专门的容器，可能在首页，尝试在upload-zone附近渲染
    const uploadZone = document.getElementById('upload-zone')
    if (uploadZone) {
      const parent = uploadZone.parentElement
      if (parent) {
        parent.innerHTML = `
          <div class="ocr-tabs-wrapper" id="ocr-tabs-container">
            <div class="ocr-tabs">
              <button class="ocr-tab ${currentOcrTab === 'recognize' ? 'active' : ''}" data-tab="recognize">
                <span class="tab-icon">📷</span>
                <span class="tab-text">识别答题卡</span>
              </button>
              <button class="ocr-tab ${currentOcrTab === 'status' ? 'active' : ''}" data-tab="status">
                <span class="tab-icon">🔧</span>
                <span class="tab-text">服务状态</span>
              </button>
            </div>
            <div class="ocr-tab-content" id="ocr-tab-content">
              <div class="upload-zone" id="upload-zone">
                <input type="file" id="file-input" accept="image/*" style="display:none;">
                <div class="upload-icon">
                  <svg viewBox="0 0 24 24" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                </div>
                <h3>点击或拖拽上传答题卡图片</h3>
                <p>支持 JPG、PNG 格式，AI自动识别学生答案</p>
              </div>
            </div>
          </div>
        `

        // 重新绑定上传事件
        const newUploadZone = document.getElementById('upload-zone')
        const newFileInput = document.getElementById('file-input')
        if (newUploadZone && newFileInput) {
          newUploadZone.addEventListener('click', () => newFileInput.click())
          newFileInput.addEventListener('change', handleFileSelect)

          newUploadZone.addEventListener('dragover', (e) => {
            e.preventDefault()
            newUploadZone.classList.add('dragover')
          })

          newUploadZone.addEventListener('dragleave', () => {
            newUploadZone.classList.remove('dragover')
          })

          newUploadZone.addEventListener('drop', (e) => {
            e.preventDefault()
            newUploadZone.classList.remove('dragover')
            if (e.dataTransfer.files.length > 0) {
              newFileInput.files = e.dataTransfer.files
              handleFileSelect({ target: newFileInput })
            }
          })
        }

        // 绑定Tab点击
        bindOcrTabs()
      }
    }
    return
  }

  bindOcrTabs()
}

/**
 * 绑定OCR Tab事件
 */
function bindOcrTabs() {
  const tabs = document.querySelectorAll('.ocr-tab')
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const tabName = tab.dataset.tab
      switchOcrTab(tabName)
    })
  })
}

/**
 * 切换OCR Tab
 */
async function switchOcrTab(tabName) {
  currentOcrTab = tabName

  // 更新Tab样式
  document.querySelectorAll('.ocr-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tabName)
  })

  const content = document.getElementById('ocr-tab-content')
  if (!content) return

  switch (tabName) {
    case 'recognize':
      renderRecognizeTab(content)
      break
    case 'status':
      await renderStatusTab(content)
      break
  }
}

/**
 * 渲染识别答题卡Tab
 */
function renderRecognizeTab(container) {
  container.innerHTML = `
    <div class="upload-zone" id="upload-zone">
      <input type="file" id="file-input" accept="image/*" style="display:none;">
      <div class="upload-icon">
        <svg viewBox="0 0 24 24" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
      </div>
      <h3>点击或拖拽上传答题卡图片</h3>
      <p>支持 JPG、PNG 格式，AI自动识别学生答案</p>
    </div>
  `

  // 重新绑定上传事件
  const uploadZone = document.getElementById('upload-zone')
  const fileInput = document.getElementById('file-input')
  if (uploadZone && fileInput) {
    uploadZone.addEventListener('click', () => fileInput.click())
    fileInput.addEventListener('change', handleFileSelect)

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
        handleFileSelect({ target: fileInput })
      }
    })
  }
}

/**
 * 渲染服务状态Tab
 */
async function renderStatusTab(container) {
  container.innerHTML = `
    <div class="service-status-section">
      <div class="status-header">
        <h3 class="status-title">🔧 解析服务状态</h3>
        <button class="btn-secondary btn-sm" onclick="teacherModule.refreshServicesStatus()">
          刷新状态
        </button>
      </div>
      <div class="status-last-check" id="status-last-check">
        ${lastStatusCheck ? `上次检测: ${formatDateTime(lastStatusCheck)}` : '点击刷新获取最新状态'}
      </div>

      <div class="service-cards" id="service-cards">
        <div class="service-card loading">
          <div class="loading-icon">🔄</div>
          <div class="loading-text">正在检测服务状态...</div>
        </div>
      </div>

      <div class="status-tips">
        <h4>说明</h4>
        <ul>
          <li><strong>OCR</strong>：文字识别服务，用于从图片中提取文字</li>
          <li><strong>MinerU</strong>：文档解析服务，用于解析PDF/DOCX/PPTX文件</li>
          <li><strong>视觉模型</strong>：多模态AI模型，用于复杂图片理解和分析</li>
        </ul>
        <p>如发现服务不可用，请检查对应服务配置或联系管理员</p>
      </div>
    </div>
  `

  // 加载服务状态
  await loadServicesStatus()
}

/**
 * 加载服务状态（通过 Hermes Agent）
 */
export async function loadServicesStatus() {
  const cardsContainer = document.getElementById('service-cards')
  if (!cardsContainer) return

  try {
    // 通过 Hermes Agent 获取服务状态
    const result = await runGetServicesStatusWithHermes()

    if (result.success) {
      servicesStatus = result.data
      lastStatusCheck = new Date()
      renderServicesStatus(servicesStatus)
    } else {
      renderServicesError(result.message || '获取状态失败')
    }
  } catch (error) {
    renderServicesError('检测失败：' + error.message)
  }
}

/**
 * 通过 Hermes Agent 获取服务状态
 */
async function runGetServicesStatusWithHermes() {
  return new Promise((resolve, reject) => {
    let hasReturned = false
    let statusResult = null

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
        statusResult = event.result
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
        const resultData = event.result || statusResult || {}
        // 格式化返回数据以匹配 renderServicesStatus 期望的格式
        // Agent 返回格式可能是: { ocr: {...}, mineru: {...}, vision: {...} }
        // 或者在 result.data 中
        let formattedData = resultData
        if (resultData.data) {
          formattedData = resultData.data
        }
        window.updateHermesThinking?.({
          type: 'final',
          result: formattedData
        })
        resolve({
          success: true,
          data: formattedData
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

    const streamResult = hermesService.executeStream(TaskType.GET_SERVICES_STATUS, {})

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
 * 刷新服务状态
 */
export async function refreshServicesStatus() {
  const lastCheckEl = document.getElementById('status-last-check')
  if (lastCheckEl) {
    lastCheckEl.textContent = '正在检测...'
  }

  await loadServicesStatus()
  Toast.success('状态已更新')
}

/**
 * 渲染服务状态卡片
 */
function renderServicesStatus(status) {
  const container = document.getElementById('service-cards')
  const lastCheckEl = document.getElementById('status-last-check')
  if (!container) return

  if (lastCheckEl) {
    lastCheckEl.textContent = `上次检测: ${formatDateTime(lastStatusCheck)}`
  }

  const services = [
    {
      key: 'ocr',
      name: 'OCR',
      icon: '📝',
      defaultInfo: '智谱GLM-OCR'
    },
    {
      key: 'mineru',
      name: 'MinerU',
      icon: '📄',
      defaultInfo: 'Magic-Doc'
    },
    {
      key: 'vision',
      name: '视觉模型',
      icon: '👁️',
      defaultInfo: '智谱GLM-4V'
    }
  ]

  container.innerHTML = services.map(service => {
    const serviceData = status[service.key] || {}
    const available = serviceData.available !== false
    const provider = serviceData.provider || service.defaultInfo
    const note = serviceData.note || ''

    return `
      <div class="service-card ${available ? 'available' : 'unavailable'}">
        <div class="service-icon">${service.icon}</div>
        <div class="service-name">${service.name}</div>
        <div class="service-status-badge ${available ? 'status-ok' : 'status-error'}">
          ${available ? '✅ 可用' : '❌ 不可用'}
        </div>
        <div class="service-provider">${provider}</div>
        ${note ? `<div class="service-note">${note}</div>` : ''}
      </div>
    `
  }).join('')
}

/**
 * 渲染服务状态错误
 */
function renderServicesError(message) {
  const container = document.getElementById('service-cards')
  const lastCheckEl = document.getElementById('status-last-check')
  if (!container) return

  if (lastCheckEl) {
    lastCheckEl.textContent = `检测失败: ${message}`
    lastCheckEl.style.color = 'var(--error)'
  }

  container.innerHTML = `
    <div class="service-card error">
      <div class="error-icon">❌</div>
      <div class="error-message">${message}</div>
      <button class="btn-secondary btn-sm" onclick="teacherModule.refreshServicesStatus()">
        重试
      </button>
    </div>
  `
}

/**
 * 格式化日期时间
 */
function formatDateTime(date) {
  if (!date) return ''
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hour = String(d.getHours()).padStart(2, '0')
  const minute = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

/**
 * 处理文件选择
 */
async function handleFileSelect(e) {
  const fileInput = e.target
  if (fileInput.files.length > 0) {
    const file = fileInput.files[0]

    // 检查是否选择了班级
    const classDropdown = document.getElementById('ocr-class-dropdown')
    const selectedClassId = classDropdown?.value
    if (!selectedClassId) {
      Toast.error('请先选择班级再上传文件')
      fileInput.value = ''
      return
    }

    // 根据文件类型确定任务类型
    const fileType = getFileTaskType(file)
    const taskConfig = getTaskConfigForFileType(fileType)

    // 保存当前选中的班级ID（全局）
    window.currentOcrClassId = selectedClassId

    // 获取班级名称用于UI
    const selectedClassName = classDropdown?.selectedOptions?.[0]?.text || '未知班级'

    // 显示 Hermes Agent 流式处理界面
    showHermesThinking({
      task: fileType,
      message: taskConfig.processingMessage.replace('{class}', selectedClassName),
      onCancel: () => {
        hermesService.cancel()
        Toast.info('已取消')
      }
    })

    try {
      let result
      if (fileType === TaskType.PDF_PARSE) {
        // PDF/Word/PPT - 使用文件路径方式
        const filePath = file.name // 实际上可能需要上传到服务器
        result = await runDocumentParseWithHermes(file, selectedClassId)
      } else if (fileType === TaskType.MULTIMODAL_ANALYSIS) {
        // 复杂图片 - 使用视觉模型
        const imageData = await readFileAsBase64(file)
        window.currentOcrImageData = imageData
        result = await runMultimodalWithHermes(imageData, selectedClassId)
      } else {
        // 普通图片 - 使用 OCR
        const imageData = await readFileAsBase64(file)
        window.currentOcrImageData = imageData
        result = await runOcrWithHermes(imageData, selectedClassId)
      }

      hideHermesThinking()

      if (result.success) {
        currentOcrPreview = result.data
        window.currentOcrPreview = result.data
        showOcrPreviewModal(result.data)
        Toast.success(taskConfig.successMessage)
      } else {
        Toast.warning(result.message || taskConfig.errorMessage)
        showOcrPreviewModal({
          success: false,
          message: result.message || '处理失败',
          students: []
        })
      }
    } catch (error) {
      hideHermesThinking()
      console.error('处理失败:', error)
      Toast.error('处理失败：' + error.message)
    }

    // 清空文件输入
    fileInput.value = ''
  }
}

/**
 * 根据文件类型确定任务类型
 */
function getFileTaskType(file) {
  const mimeType = file.type.toLowerCase()
  const fileName = file.name.toLowerCase()

  // 图片类型
  if (mimeType.startsWith('image/')) {
    // 检查是否为复杂图片（可以扩展检测逻辑）
    // 目前简单处理：所有图片都走 OCR
    return TaskType.OCR_RECOGNIZE
  }

  // PDF
  if (mimeType === 'application/pdf' || fileName.endsWith('.pdf')) {
    return TaskType.PDF_PARSE
  }

  // Word
  if (mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
      fileName.endsWith('.docx')) {
    return TaskType.PDF_PARSE // 复用 PDF_PARSE 任务类型
  }

  // PowerPoint
  if (mimeType === 'application/vnd.openxmlformats-officedocument.presentationml.presentation' ||
      fileName.endsWith('.pptx')) {
    return TaskType.PDF_PARSE
  }

  // 默认走 OCR
  return TaskType.OCR_RECOGNIZE
}

/**
 * 获取任务配置
 */
function getTaskConfigForFileType(taskType) {
  const configs = {
    [TaskType.OCR_RECOGNIZE]: {
      processingMessage: '正在识别答题卡...',
      successMessage: '识别完成，请确认结果',
      errorMessage: '识别失败，请检查结果或点击"AI重新分析"按钮'
    },
    [TaskType.PDF_PARSE]: {
      processingMessage: '正在解析文档...',
      successMessage: '文档解析完成，请确认结果',
      errorMessage: '文档解析失败'
    },
    [TaskType.MULTIMODAL_ANALYSIS]: {
      processingMessage: '正在使用视觉模型分析图片...',
      successMessage: '分析完成，请确认结果',
      errorMessage: '图片分析失败'
    }
  }
  return configs[taskType] || configs[TaskType.OCR_RECOGNIZE]
}

/**
 * 使用 Hermes Agent 执行 OCR 识别（流式）
 * @param {string} imageData - 图片base64数据
 * @param {string} classId - 选中的班级ID
 */
async function runOcrWithHermes(imageData, classId) {
  return new Promise((resolve, reject) => {
    let hasReturned = false
    let finalResult = null

    // 设置事件回调
    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking:', event.content)
      // 更新 HermesThinking UI
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
      // OCR 可能需要确认低置信度答案
    })

    hermesService.on('final', (event) => {
      if (!hasReturned) {
        hasReturned = true
        finalResult = event.result || event
        window.updateHermesThinking?.({
          type: 'final',
          result: finalResult
        })
        resolve({
          success: true,
          data: finalResult
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

    // 执行流式任务（包含选中的班级ID）
    const streamResult = hermesService.executeStream(TaskType.OCR_RECOGNIZE, {
      image: imageData,
      questions: getDefaultQuestions(),
      class_id: classId || window.currentOcrClassId
    })

    if (!streamResult.success) {
      reject(new Error(streamResult.error || 'Agent启动失败'))
      return
    }

    // 处理流式响应
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
 * 读取文件为 Base64
 */
function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      // 返回包含 data URL 前缀的完整字符串
      // 实际使用时需要去掉前缀
      resolve(e.target.result)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/**
 * 获取默认题目列表
 */
function getDefaultQuestions() {
  return [
    { number: "1", correct_answer: "A", knowledge_points: ["氧化还原反应"], max_score: 6, content: "题目1" },
    { number: "2", correct_answer: "B", knowledge_points: ["电解质"], max_score: 6, content: "题目2" },
    { number: "3", correct_answer: "C", knowledge_points: ["离子反应"], max_score: 6, content: "题目3" },
    { number: "4", correct_answer: "D", knowledge_points: ["化学平衡"], max_score: 6, content: "题目4" },
    { number: "5", correct_answer: "A", knowledge_points: ["氧化还原反应"], max_score: 6, content: "题目5" },
    { number: "6", correct_answer: "B", knowledge_points: ["电解质"], max_score: 6, content: "题目6" },
    { number: "7", correct_answer: "C", knowledge_points: ["离子反应"], max_score: 6, content: "题目7" },
    { number: "8", correct_answer: "A", knowledge_points: ["化学平衡"], max_score: 6, content: "题目8" },
    { number: "9", correct_answer: "B", knowledge_points: ["氧化还原反应"], max_score: 6, content: "题目9" },
    { number: "10", correct_answer: "D", knowledge_points: ["电解质"], max_score: 6, content: "题目10" }
  ]
}

/**
 * 显示OCR预览弹窗
 */
export function showOcrPreviewModal(previewResult) {
  const modal = document.getElementById('ocr-preview-modal')
  if (!modal) return

  const statusEl = document.getElementById('ocr-status')
  const confidenceEl = document.getElementById('ocr-confidence')
  const messageEl = document.getElementById('ocr-message')
  const rawTextSection = document.getElementById('ocr-raw-text-section')
  const rawTextEl = document.getElementById('ocr-raw-text')
  const answersListEl = document.getElementById('ocr-answers-list')
  const llmAnalysisEl = document.getElementById('ocr-llm-analysis')
  const llmListEl = document.getElementById('ocr-llm-list')
  const editListEl = document.getElementById('ocr-edit-list')

  // 显示消息
  if (messageEl) {
    messageEl.textContent = previewResult.message || ''
  }

  // 填充学生身份确认区域
  const studentIdInput = document.getElementById('ocr-confirm-student-id')
  const studentNameInput = document.getElementById('ocr-confirm-student-name')
  if (previewResult.students && previewResult.students.length > 0) {
    const student = previewResult.students[0]
    const recognizedStudentId = student.student_id || ''
    const recognizedStudentName = student.student_name || ''

    if (studentIdInput) studentIdInput.value = recognizedStudentId
    if (studentNameInput) studentNameInput.value = recognizedStudentName

    // 保存到全局状态
    currentOcrStudentId = recognizedStudentId
    currentOcrStudentName = recognizedStudentName
  } else {
    if (studentIdInput) studentIdInput.value = ''
    if (studentNameInput) studentNameInput.value = ''
    currentOcrStudentId = ''
    currentOcrStudentName = ''
  }

  // 显示原始识别文本
  if (previewResult.raw_text && previewResult.raw_text.length > 0) {
    rawTextSection.style.display = 'block'
    rawTextEl.textContent = previewResult.raw_text
  } else {
    rawTextSection.style.display = 'none'
  }

  // 更新状态
  if (previewResult.students && previewResult.students.length > 0) {
    const student = previewResult.students[0]
    const hasAnswers = student.answers && Object.keys(student.answers).length > 0

    if (hasAnswers) {
      statusEl.className = 'status done'
      statusEl.textContent = '✓ 识别成功'
      confidenceEl.textContent = `置信度: ${(student.confidence * 100).toFixed(1)}%`

      // 渲染答案列表
      renderAnswerList(student, previewResult)
    } else {
      // 没有识别到有效答案
      statusEl.className = 'status warning'
      statusEl.textContent = '未识别到有效答案'
      confidenceEl.textContent = `原始文本: ${(previewResult.raw_text || '无').substring(0, 50)}...`
      renderEmptyAnswers()
    }
  } else {
    statusEl.className = 'status warning'
    statusEl.textContent = '未识别到有效答案'
    confidenceEl.textContent = ''
    renderEmptyAnswers()
  }

  // 显示LLM分析结果
  if (previewResult.llm_checks && previewResult.llm_checks.length > 0) {
    if (llmAnalysisEl) llmAnalysisEl.style.display = 'block'
    renderLlmAnalysis(previewResult.llm_checks)
  } else {
    if (llmAnalysisEl) llmAnalysisEl.style.display = 'none'
  }

  // 显示弹窗
  modal.style.display = 'flex'
}

/**
 * 渲染答案列表
 */
function renderAnswerList(student, previewResult) {
  const answersListEl = document.getElementById('ocr-answers-list')
  const editListEl = document.getElementById('ocr-edit-list')
  if (!answersListEl || !editListEl) return

  let answersHtml = ''
  let editHtml = ''

  for (const [qNum, answer] of Object.entries(student.answers || {})) {
    const isLowConfidence = student.low_confidence_answers?.some(
      lca => lca.question_number === qNum
    )

    const llmCheck = previewResult.llm_checks?.find(
      lc => lc.question_number === qNum
    )

    answersHtml += `
      <div style="display:flex;align-items:center;gap:12px;padding:8px 12px;background:var(--bg);border-radius:6px;margin-bottom:6px;">
        <span style="font-weight:600;min-width:60px;">第${qNum}题</span>
        <span style="flex:1;">${answer || '-'}</span>
        ${isLowConfidence ? '<span class="status warning">低置信度</span>' : ''}
        ${llmCheck && !llmCheck.is_consistent ? '<span class="status error">疑似错误</span>' : ''}
        ${llmCheck ? `<span style="font-size:0.6875rem;color:var(--text-muted);">LLM建议:${llmCheck.llm_check}</span>` : ''}
      </div>
    `

    editHtml += `
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
        <span style="font-weight:600;min-width:60px;">第${qNum}题</span>
        <input type="text" value="${answer || ''}"
          onchange="window.updateOcrAnswer('${qNum}', this.value)"
          style="flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:0.875rem;"
          placeholder="输入答案">
        ${llmCheck && !llmCheck.is_consistent ? `<span style="font-size:0.75rem;color:var(--error);white-space:nowrap;">LLM建议:${llmCheck.llm_check}</span>` : ''}
      </div>
    `

    currentOcrAnswers[qNum] = answer || ''
  }

  answersListEl.innerHTML = answersHtml
  editListEl.innerHTML = editHtml
}

/**
 * 渲染无答案状态
 */
function renderEmptyAnswers() {
  const answersListEl = document.getElementById('ocr-answers-list')
  const editListEl = document.getElementById('ocr-edit-list')
  if (!answersListEl || !editListEl) return

  answersListEl.innerHTML = `
    <div style="padding:16px;background:var(--bg);border-radius:8px;text-align:center;">
      <div style="font-size:2rem;margin-bottom:8px;">📋</div>
      <div style="color:var(--text-muted);margin-bottom:12px;">未从图片中识别到有效答题卡数据</div>
      <div style="font-size:0.75rem;color:var(--text-secondary);">可能原因：图片不清晰、格式不支持、答题卡放置不正确</div>
    </div>
  `

  editListEl.innerHTML = '<div style="font-size:0.8125rem;color:var(--text-secondary);margin-bottom:12px;">请手动输入学生答题结果：</div>'
  for (let i = 1; i <= 10; i++) {
    editListEl.innerHTML += `
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
        <span style="font-weight:600;min-width:60px;">第${i}题</span>
        <input type="text" id="manual-answer-${i}"
          onchange="window.updateOcrAnswer('${i}', this.value)"
          style="flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:0.875rem;"
          placeholder="输入答案(A/B/C/D)">
      </div>
    `
  }
}

/**
 * 渲染LLM分析结果
 */
function renderLlmAnalysis(llmChecks) {
  const llmListEl = document.getElementById('ocr-llm-list')
  if (!llmListEl) return

  let html = ''
  for (const check of llmChecks) {
    const statusClass = check.is_consistent ? 'success' : 'error'
    const statusText = check.is_consistent ? '✓ 一致' : '✗ 不一致'
    html += `
      <div style="padding:10px 12px;background:var(--bg);border-radius:6px;margin-bottom:8px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
          <span style="font-weight:600;">第${check.question_number}题</span>
          <span class="status ${statusClass}">${statusText}</span>
        </div>
        <div style="font-size:0.8125rem;color:var(--text-secondary);">${check.llm_check || '无建议'}</div>
      </div>
    `
  }
  llmListEl.innerHTML = html
}

/**
 * 更新OCR答案
 */
export function updateOcrAnswer(questionNumber, value) {
  currentOcrAnswers[questionNumber] = value
}

/**
 * 更新确认的学生学号
 */
export function updateOcrStudentId(value) {
  currentOcrStudentId = value
}

/**
 * 更新确认的学生姓名
 */
export function updateOcrStudentName(value) {
  currentOcrStudentName = value
}

/**
 * 确认OCR结果并生成统计
 */
export async function confirmOcrResults() {
  const previewResult = window.currentOcrPreview
  if (!previewResult) {
    Toast.error('没有可确认的OCR结果')
    return
  }

  // 获取确认后的学生身份
  const confirmedStudentId = currentOcrStudentId || previewResult.students?.[0]?.student_id || 'unknown'
  const confirmedStudentName = currentOcrStudentName || previewResult.students?.[0]?.student_name || '未知学生'

  // 检查是否有有效答案
  const hasManualAnswers = currentOcrAnswers && Object.keys(currentOcrAnswers).length > 0
  if (!hasManualAnswers) {
    Toast.error('无有效答案，请先识别或手动输入答案')
    return
  }

  try {
    Toast.info('正在确认答题卡并生成统计...')

    // 构建确认请求 - 使用正确的 ExamStatsRequest 格式
    const confirmData = {
      preview_id: previewResult.preview_id || ('preview_' + Date.now()),
      class_id: window.currentOcrClassId || getCurrentOcrClassId(),  // 使用选中的班级ID
      exam_name: '答题卡识别_' + new Date().toLocaleDateString(),
      exam_date: new Date().toISOString().split('T')[0],
      questions: [
        { number: "1", correct_answer: "A", knowledge_points: ["氧化还原反应"], max_score: 6, content: "题目1" },
        { number: "2", correct_answer: "B", knowledge_points: ["电解质"], max_score: 6, content: "题目2" },
        { number: "3", correct_answer: "C", knowledge_points: ["离子反应"], max_score: 6, content: "题目3" },
        { number: "4", correct_answer: "D", knowledge_points: ["化学平衡"], max_score: 6, content: "题目4" },
        { number: "5", correct_answer: "A", knowledge_points: ["氧化还原反应"], max_score: 6, content: "题目5" },
        { number: "6", correct_answer: "B", knowledge_points: ["电解质"], max_score: 6, content: "题目6" },
        { number: "7", correct_answer: "C", knowledge_points: ["离子反应"], max_score: 6, content: "题目7" },
        { number: "8", correct_answer: "A", knowledge_points: ["化学平衡"], max_score: 6, content: "题目8" },
        { number: "9", correct_answer: "B", knowledge_points: ["氧化还原反应"], max_score: 6, content: "题目9" },
        { number: "10", correct_answer: "D", knowledge_points: ["电解质"], max_score: 6, content: "题目10" }
      ],
      // 使用确认后的学生身份
      ocr_results: [{
        student_id: confirmedStudentId,
        student_name: confirmedStudentName,
        answers: { ...currentOcrAnswers }
      }]
    }

    // 调用确认接口
    const result = await api.post('/api/ocr/confirm', confirmData)

    if (result.success) {
      Toast.success('答题卡确认成功！')

      // 触发学情诊断和记忆持久化（通过 Hermes Agent）
      await persistStudentDiagnosis(confirmedStudentId, confirmedStudentName, result)

      closeOcrPreviewModal()

      // 触发统计更新
      if (typeof loadStatistics === 'function') {
        loadStatistics()
      }
    } else {
      Toast.error(result.message || '确认失败')
    }
  } catch (error) {
    Toast.error('确认失败：' + error.message)
  }
}

/**
 * 通过 Hermes Agent 持久化学情诊断结果到学生记忆
 */
async function persistStudentDiagnosis(studentId, studentName, examResult) {
  if (!studentId || studentId === 'unknown') {
    console.log('无效学生ID，跳过学情持久化')
    return
  }

  try {
    Toast.info('正在更新学生学情记忆...')

    // 通过 Hermes Agent 调用 memory_on_diagnosis_completed 工具
    // 这会让学生画像持续进化，记录每次考试的诊断结果
    const diagnosisData = {
      student_id: studentId,
      barrier_type: {
        concept: 0.33,
        reading: 0.33,
        expression: 0.34
      },
      dominant_barrier: 'concept',
      weak_kps: extractWeakKnowledgePoints(examResult)
    }

    // 调用 Hermes Agent 执行记忆持久化
    await runMemoryPersistenceWithHermes(diagnosisData)

    Toast.success('学情记忆已更新')
  } catch (error) {
    console.error('学情持久化失败:', error)
    // 不影响主流程，只是警告
  }
}

/**
 * 从考试结果中提取薄弱知识点
 */
function extractWeakKnowledgePoints(examResult) {
  const weakKps = []

  if (examResult.question_stats) {
    // 按错误率排序，取错误率最高的知识点
    const sortedQuestions = [...examResult.question_stats].sort(
      (a, b) => b.error_rate - a.error_rate
    )

    for (const q of sortedQuestions.slice(0, 3)) {
      if (q.error_rate > 0.3 && q.knowledge_points) {
        weakKps.push(...q.knowledge_points)
      }
    }
  }

  return [...new Set(weakKps)] // 去重
}

/**
 * 通过 Hermes Agent 持久化学情记忆
 */
async function runMemoryPersistenceWithHermes(diagnosisData) {
  return new Promise((resolve, reject) => {
    let hasReturned = false

    // 设置事件回调
    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking for memory:', event.content)
    })

    hermesService.on('tool_call', (event) => {
      console.log('Hermes tool call for memory:', event.tool, event.params)
    })

    hermesService.on('tool_result', (event) => {
      console.log('Hermes tool result for memory:', event.result)
    })

    hermesService.on('final', (event) => {
      if (!hasReturned) {
        hasReturned = true
        resolve({
          success: true,
          data: event.result
        })
      }
    })

    hermesService.on('error', (event) => {
      if (!hasReturned) {
        hasReturned = true
        console.error('Hermes memory persistence error:', event.error)
        reject(new Error(event.error || '记忆持久化失败'))
      }
    })

    // 注意：这里需要一个新的 TaskType 来执行记忆持久化
    // 由于现有 TaskType 没有专门的记忆持久化任务，我们使用 ANALYZE_BARRIER 作为载体
    // 或者直接调用 API
    // 为了简单起见，这里直接通过 API 调用 memory 工具

    // 构建 prompt 让 Agent 调用 memory_on_diagnosis_completed
    const prompt = `请将学生的诊断结果持久化到学情记忆中。

学生信息：
- 学生ID: ${diagnosisData.student_id}
- 障碍类型: ${diagnosisData.dominant_barrier}
- 薄弱知识点: ${diagnosisData.weak_kps.join('、') || '暂无'}

请调用 memory_on_diagnosis_completed 工具，将这次诊断结果记录到学生的 memory.md 文件中。`

    // 由于 TaskType 没有专门的记忆持久化，我们通过聊天方式执行
    // 但 Hermes Agent 目前没有这种任务类型，所以这里改为直接调用 API
    // 实际上记忆持久化应该由后端在 /api/ocr/confirm 时自动完成

    // 这里我们简单地发送一个请求到后端，让后端处理记忆持久化
    // 因为记忆持久化不需要流式输出，所以直接用 API 调用更简单
    api.post('/api/memory/diagnosis-complete', {
      student_id: diagnosisData.student_id,
      barrier_type: diagnosisData.barrier_type,
      dominant_barrier: diagnosisData.dominant_barrier,
      weak_kps: diagnosisData.weak_kps
    }).then(res => {
      if (!hasReturned) {
        hasReturned = true
        resolve({ success: true, data: res })
      }
    }).catch(err => {
      if (!hasReturned) {
        hasReturned = true
        reject(err)
      }
    })
  })
}

/**
 * AI重新分析（使用 Hermes Agent）
 */
export async function retryOcrWithLLM() {
  const imageData = window.currentOcrImageData
  if (!imageData) {
    Toast.error('没有图片数据')
    return
  }

  // 显示流式处理界面
  showHermesThinking({
    task: TaskType.OCR_RECOGNIZE,
    message: '正在重新分析...',
    onCancel: () => {
      hermesService.cancel()
      Toast.info('已取消')
    }
  })

  try {
    const result = await runOcrWithHermes(imageData)
    hideHermesThinking()

    if (result.success) {
      window.currentOcrPreview = result.data
      showOcrPreviewModal(result.data)
      Toast.success('重新分析完成')
    } else {
      Toast.error(result.message || '重新分析失败')
    }
  } catch (error) {
    hideHermesThinking()
    Toast.error('重新分析失败：' + error.message)
  }
}

/**
 * 关闭OCR预览弹窗
 */
export function closeOcrPreviewModal() {
  const modal = document.getElementById('ocr-preview-modal')
  if (modal) {
    modal.style.display = 'none'
  }
}

// ============================================
// 班级选择功能
// ============================================

/**
 * 初始化OCR班级选择下拉框
 * 调用时机：在页面加载完成、OCR Tab切换时
 */
export async function initOcrClassSelect() {
  const container = document.getElementById('ocr-class-select')
  const dropdown = document.getElementById('ocr-class-dropdown')
  if (!container || !dropdown) return

  try {
    // 获取当前用户的班级列表
    const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
    let classes = []

    if (user.role === 'admin' || user.role === '教务管理员') {
      // 管理员/教务管理员可以选所有班级
      const result = await classService.getClassList()
      classes = result.classes || []
    } else if (user.role === '学科组长' || user.role === 'teacher') {
      // 学科组长/教师获取自己关联的班级
      const result = await userService.getTeacherClasses(user.teacher_id)
      classes = result.classes || []
    }

    // 填充下拉框
    dropdown.innerHTML = '<option value="">请选择班级...</option>' +
      classes.map(c => `<option value="${c.class_id}">${c.class_name || c.name}</option>`).join('')

    // 显示容器
    container.classList.add('visible')
  } catch (error) {
    console.error('加载班级列表失败:', error)
  }
}

/**
 * 处理班级选择
 * 当用户没有选择班级时，点击上传区域会提示
 */
export function handleOcrClassSelect() {
  const dropdown = document.getElementById('ocr-class-dropdown')
  if (!dropdown?.value) {
    Toast.error('请先选择班级再上传文件')
    return false
  }
  return true
}

/**
 * 获取当前选中的班级ID
 */
export function getCurrentOcrClassId() {
  const dropdown = document.getElementById('ocr-class-dropdown')
  return dropdown?.value || null
}

/**
 * 使用 Hermes Agent 执行文档解析（PDF/Word/PPT）
 * @param {File} file - 文件对象
 * @param {string} classId - 选中的班级ID
 */
async function runDocumentParseWithHermes(file, classId) {
  return new Promise((resolve, reject) => {
    let hasReturned = false

    // 设置事件回调
    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking for doc parse:', event.content)
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
        const result = event.result || {}
        // 确保结果中包含 class_id
        if (typeof result === 'object') {
          result.class_id = classId || window.currentOcrClassId
        }
        window.updateHermesThinking?.({
          type: 'final',
          result: result
        })
        resolve({
          success: true,
          data: result
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

    // 执行文档解析任务
    const streamResult = hermesService.executeStream(TaskType.PDF_PARSE, {
      file_name: file.name,
      file_size: file.size,
      mime_type: file.type,
      class_id: classId || window.currentOcrClassId
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
 * 使用 Hermes Agent 执行视觉模型分析（复杂图片）
 * @param {string} imageData - 图片base64数据
 * @param {string} classId - 选中的班级ID
 */
async function runMultimodalWithHermes(imageData, classId) {
  return new Promise((resolve, reject) => {
    let hasReturned = false

    // 设置事件回调
    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking for multimodal:', event.content)
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
        const result = event.result || {}
        if (typeof result === 'object') {
          result.class_id = classId || window.currentOcrClassId
        }
        window.updateHermesThinking?.({
          type: 'final',
          result: result
        })
        resolve({
          success: true,
          data: result
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

    // 执行多模态分析任务
    const streamResult = hermesService.executeStream(TaskType.MULTIMODAL_ANALYSIS, {
      image: imageData,
      class_id: classId || window.currentOcrClassId
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

// 导出全局函数供HTML调用
if (typeof window !== 'undefined') {
  // OCR功能
  window.updateOcrAnswer = updateOcrAnswer
  window.updateOcrStudentId = updateOcrStudentId
  window.updateOcrStudentName = updateOcrStudentName
  window.confirmOcrResults = confirmOcrResults
  window.retryOcrWithLLM = retryOcrWithLLM
  window.closeOcrPreviewModal = closeOcrPreviewModal

  // 班级选择
  window.initOcrClassSelect = initOcrClassSelect
  window.handleOcrClassSelect = handleOcrClassSelect
  window.getCurrentOcrClassId = getCurrentOcrClassId

  // 服务状态
  window.teacherModule = window.teacherModule || {}
  window.teacherModule.refreshServicesStatus = refreshServicesStatus
  window.teacherModule.loadServicesStatus = loadServicesStatus
  window.teacherModule.initOcrUpload = initOcrUpload
}
