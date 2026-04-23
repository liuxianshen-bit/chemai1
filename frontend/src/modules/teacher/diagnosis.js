/**
 * 教师端 - 诊断模块
 * 使用 Hermes Agent 实现真正的流式诊断和学习计划生成
 */
import { diagnosisService } from '../../services/index.js'
import { hermesService, TaskType } from '../../services/hermes.js'
import { Toast, showLoading, hideLoading, showHermesThinking, hideHermesThinking } from '../../components/index.js'

// 全局状态
let currentDiagnosisData = null

/**
 * 初始化诊断模块
 */
export async function initDiagnosisModule() {
  const container = document.getElementById('diagnosis-threshold')
  if (!container) return

  // 确保配置面板显示，诊断面板隐藏
  const configPanel = document.getElementById('diagnosis-config-panel')
  if (configPanel) configPanel.style.display = 'block'

  const planPanel = document.getElementById('diagnosis-plan')
  if (planPanel) planPanel.style.display = 'none'

  await loadDiagnosisConfig()
}

/**
 * 加载诊断配置
 */
export async function loadDiagnosisConfig() {
  try {
    // 加载障碍阈值配置
    const result = await diagnosisService.getBarrierConfig()
    if (result.success) {
      renderDiagnosisConfig(result.data)
    }
  } catch (error) {
    console.error('加载诊断配置失败:', error)
  }
}

/**
 * 渲染诊断配置
 */
function renderDiagnosisConfig(config) {
  const container = document.getElementById('diagnosis-threshold')
  if (!container) return

  container.innerHTML = `
    <div class="diagnosis-config">
      <h3>障碍诊断阈值设置</h3>
      <div class="config-grid">
        <div class="config-item">
          <label>概念理解障碍阈值</label>
          <input type="number" id="threshold-concept" value="${config.concept_threshold || 0.3}" min="0" max="1" step="0.1">
        </div>
        <div class="config-item">
          <label>审题障碍阈值</label>
          <input type="number" id="threshold-reading" value="${config.reading_threshold || 0.25}" min="0" max="1" step="0.1">
        </div>
        <div class="config-item">
          <label>表述障碍阈值</label>
          <input type="number" id="threshold-expression" value="${config.expression_threshold || 0.2}" min="0" max="1" step="0.1">
        </div>
      </div>
      <button class="btn-primary" onclick="saveDiagnosisConfig()">保存配置</button>
    </div>
  `
}

/**
 * 保存诊断配置
 */
export async function saveDiagnosisConfig() {
  const conceptThreshold = parseFloat(document.getElementById('threshold-concept')?.value) || 0.3
  const readingThreshold = parseFloat(document.getElementById('threshold-reading')?.value) || 0.25
  const expressionThreshold = parseFloat(document.getElementById('threshold-expression')?.value) || 0.2

  showLoading()

  try {
    const result = await diagnosisService.updateBarrierConfig({
      concept_threshold: conceptThreshold,
      reading_threshold: readingThreshold,
      expression_threshold: expressionThreshold
    })

    if (result.success) {
      Toast.success('配置已保存')
    } else {
      Toast.error('保存失败')
    }
  } catch (error) {
    Toast.error('保存失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 加载班级诊断结果（使用 Hermes Agent 流式）
 */
export async function loadClassDiagnosis(classId, examId) {
  showHermesThinking({
    task: TaskType.ANALYZE_BARRIER,
    message: '正在分析学生答题数据...',
    onCancel: () => {
      hermesService.cancel()
      Toast.info('已取消诊断')
    }
  })

  try {
    // 使用 Hermes Agent 执行障碍诊断
    const result = await runBarrierAnalysis(classId, examId)

    hideHermesThinking()

    if (result.success) {
      currentDiagnosisData = result.data
      renderClassDiagnosis(result.data)
      Toast.success('诊断完成')
    } else {
      Toast.error(result.message || '诊断失败')
    }
  } catch (error) {
    hideHermesThinking()
    Toast.error('诊断失败：' + error.message)
  }
}

/**
 * 使用 Hermes Agent 执行障碍诊断（流式）
 */
async function runBarrierAnalysis(classId, examId) {
  return new Promise((resolve, reject) => {
    let hasReturned = false
    let diagnosisData = null

    // 设置事件回调
    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking:', event.content)
      window.updateHermesThinking?.({
        type: 'thinking',
        content: event.content
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
      if (event.result) {
        diagnosisData = { ...diagnosisData, ...event.result }
      }
      window.updateHermesThinking?.({
        type: 'tool_result',
        result: event.result
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
    })

    hermesService.on('final', (event) => {
      if (!hasReturned) {
        hasReturned = true
        resolve({
          success: true,
          data: event.result || diagnosisData
        })
      }
    })

    hermesService.on('error', (event) => {
      if (!hasReturned) {
        hasReturned = true
        reject(new Error(event.error || event.message || 'Agent执行失败'))
      }
    })

    // 执行流式任务
    const streamResult = hermesService.executeStream(TaskType.ANALYZE_BARRIER, {
      class_id: classId,
      exam_record_id: examId
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
 * 渲染班级诊断结果
 */
function renderClassDiagnosis(data) {
  const container = document.getElementById('diagnosis-plan')
  if (!container) return

  // 隐藏配置面板，显示诊断结果面板
  const configPanel = document.getElementById('diagnosis-config-panel')
  if (configPanel) configPanel.style.display = 'none'

  // 渲染障碍分布
  const distributionContainer = document.getElementById('diagnosis-obstacle-distribution')
  if (distributionContainer && data.obstacle_distribution) {
    distributionContainer.innerHTML = renderObstacleChart(data.obstacle_distribution)
  }

  // 渲染学生列表
  const studentListContainer = document.getElementById('diagnosis-student-list')
  if (studentListContainer && data.students) {
    renderStudentDiagnosisList(data.students)
  }

  container.style.display = 'block'
}

/**
 * 渲染障碍分布图表
 */
function renderObstacleChart(distribution) {
  const total = distribution.concept + distribution.reading + distribution.expression

  return `
    <div class="obstacle-chart">
      <div class="chart-bar">
        <div class="bar concept" style="width: ${(distribution.concept / total * 100)}%"></div>
        <div class="bar reading" style="width: ${(distribution.reading / total * 100)}%"></div>
        <div class="bar expression" style="width: ${(distribution.expression / total * 100)}%"></div>
      </div>
      <div class="chart-legend">
        <span class="legend-item concept">概念理解型: ${distribution.concept}</span>
        <span class="legend-item reading">审题障碍型: ${distribution.reading}</span>
        <span class="legend-item expression">表述障碍型: ${distribution.expression}</span>
      </div>
    </div>
  `
}

/**
 * 渲染学生诊断列表
 */
function renderStudentDiagnosisList(students) {
  const container = document.getElementById('diagnosis-student-list')
  if (!container) return

  container.innerHTML = students.map(student => `
    <div class="student-diagnosis-card" onclick="showStudentDiagnosis('${student.id}')">
      <div class="student-avatar">${(student.name || 'U').charAt(0)}</div>
      <div class="student-info">
        <h4>${student.name}</h4>
        <p>障碍类型: ${getBarrierTypeName(student.primary_barrier)}</p>
      </div>
      <div class="barrier-tag ${student.primary_barrier}">${getBarrierLevelName(student.barrier_level)}</div>
    </div>
  `).join('')
}

/**
 * 显示学生详细诊断
 */
export async function showStudentDiagnosis(studentId) {
  const container = document.getElementById('diagnosis-student-detail')
  const studentInfo = document.getElementById('diagnosis-student-info')
  const planContent = document.getElementById('diagnosis-plan-content')

  if (!container) return

  showLoading()

  try {
    const result = await diagnosisService.getStudentDiagnosis(studentId)

    if (result.success) {
      const student = result.data

      if (studentInfo) {
        studentInfo.innerHTML = `
          <div class="student-detail-header">
            <h3>${student.name}</h3>
            <span class="barrier-tag ${student.primary_barrier}">${getBarrierTypeName(student.primary_barrier)}</span>
          </div>
          <div class="student-stats">
            <div class="stat">
              <span class="label">正确率</span>
              <span class="value">${(student.accuracy * 100).toFixed(1)}%</span>
            </div>
            <div class="stat">
              <span class="label">障碍等级</span>
              <span class="value">${getBarrierLevelName(student.barrier_level)}</span>
            </div>
          </div>
          <div class="student-diagnosis-actions">
            <button class="btn-primary btn-sm" onclick="generateStudentLearningPlan('${student.id}')">
              <span class="btn-icon">📖</span>生成学习计划
            </button>
            <button class="btn-secondary btn-sm" onclick="applyStudentLearningPlan('${student.id}')" id="btn-apply-plan" style="display:none;">
              <span class="btn-icon">✅</span>应用到学生
            </button>
            <button class="btn-secondary btn-sm" onclick="sendPlanToParentHandler('${student.id}')" id="btn-send-plan" style="display:none;">
              <span class="btn-icon">📱</span>发送给家长
            </button>
          </div>
        `
      }

      // 加载学生当前学习计划
      const planResult = await diagnosisService.getStudentLearningPlan(studentId)

      if (planContent) {
        if (planResult.success && planResult.data) {
          planContent.innerHTML = renderLearningPlanPreview(planResult.data, student.id)
          // 显示应用和发送按钮
          document.getElementById('btn-apply-plan')?.style.setProperty('display', 'inline-block')
          document.getElementById('btn-send-plan')?.style.setProperty('display', 'inline-block')
        } else {
          planContent.innerHTML = `
            <div class="plan-empty-state">
              <div class="empty-icon">📋</div>
              <p>暂无学习计划</p>
              <p class="empty-hint">点击上方"生成学习计划"按钮为该学生创建个性化学习方案</p>
            </div>
          `
        }
      }

      container.style.display = 'block'
    } else {
      Toast.error('加载失败')
    }
  } catch (error) {
    Toast.error('加载失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 生成学生学习计划（使用 Hermes Agent 流式）
 */
export async function generateStudentLearningPlan(studentId) {
  const planContent = document.getElementById('diagnosis-plan-content')
  if (!planContent) return

  showHermesThinking({
    task: TaskType.GENERATE_LEARNING_PLAN,
    message: '正在生成个性化学习计划...',
    onCancel: () => {
      hermesService.cancel()
      Toast.info('已取消')
    }
  })

  try {
    // 获取学生诊断数据
    const diagnosisResult = await diagnosisService.getStudentDiagnosis(studentId)
    if (!diagnosisResult.success) {
      throw new Error(diagnosisResult.message || '获取学生诊断信息失败')
    }

    const studentData = diagnosisResult.data

    // 使用 Hermes Agent 执行学习计划生成
    const result = await runLearningPlanGeneration(studentId, {
      barrier_type: studentData.primary_barrier,
      weak_knowledge_points: studentData.weak_knowledge_points || [],
      recent_performance: {
        accuracy: studentData.accuracy,
        barrier_level: studentData.barrier_level
      }
    })

    hideHermesThinking()

    if (result.success && result.data) {
      planContent.innerHTML = renderLearningPlanPreview(result.data, studentId, true)
      Toast.success('学习计划生成成功')
      // 显示应用和发送按钮
      document.getElementById('btn-apply-plan')?.style.setProperty('display', 'inline-block')
      document.getElementById('btn-send-plan')?.style.setProperty('display', 'inline-block')
    } else {
      throw new Error(result.message || '生成学习计划失败')
    }
  } catch (error) {
    hideHermesThinking()
    planContent.innerHTML = `
      <div class="plan-error-state">
        <div class="error-icon">❌</div>
        <p>生成失败</p>
        <p class="error-hint">${error.message}</p>
      </div>
    `
    Toast.error('生成失败：' + error.message)
  }
}

/**
 * 使用 Hermes Agent 执行学习计划生成（流式）
 */
async function runLearningPlanGeneration(studentId, params) {
  return new Promise((resolve, reject) => {
    let hasReturned = false
    let planData = null

    // 设置事件回调
    hermesService.on('thinking', (event) => {
      console.log('Hermes thinking:', event.content)
      window.updateHermesThinking?.({
        type: 'thinking',
        content: event.content
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
      if (event.result) {
        planData = { ...planData, ...event.result }
      }
      window.updateHermesThinking?.({
        type: 'tool_result',
        result: event.result
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
    })

    hermesService.on('final', (event) => {
      if (!hasReturned) {
        hasReturned = true
        resolve({
          success: true,
          data: event.result || planData
        })
      }
    })

    hermesService.on('error', (event) => {
      if (!hasReturned) {
        hasReturned = true
        reject(new Error(event.error || event.message || 'Agent执行失败'))
      }
    })

    // 执行流式任务
    const streamResult = hermesService.executeStream(TaskType.GENERATE_LEARNING_PLAN, {
      student_id: studentId,
      ...params
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
 * 渲染学习计划预览
 */
function renderLearningPlanPreview(planData, studentId, isNewlyGenerated = false) {
  const plan = planData.plan || planData
  if (!plan) return '<p class="empty">暂无学习计划</p>'

  return `
    <div class="learning-plan-preview ${isNewlyGenerated ? 'newly-generated' : ''}">
      ${isNewlyGenerated ? '<div class="plan-generated-badge">✨ 新生成</div>' : ''}
      <div class="plan-header-info">
        <h4 class="plan-title">${plan.plan_title || '个性化学习计划'}</h4>
        <span class="plan-period-badge">${plan.plan_period || '2周'}</span>
      </div>

      ${plan.barrier_interventions && plan.barrier_interventions.length > 0 ? `
        <div class="plan-section">
          <h5 class="section-sub-title">障碍干预策略</h5>
          <div class="intervention-list">
            ${plan.barrier_interventions.map(item => `
              <div class="intervention-item ${item.barrier}">
                <span class="intervention-barrier-tag ${item.barrier}">${getBarrierTypeName(item.barrier)}</span>
                <div class="intervention-detail">
                  <p class="intervention-strategy">${item.strategy || ''}</p>
                  ${item.practice_tips ? `<p class="intervention-tips">💡 ${item.practice_tips}</p>` : ''}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}

      ${plan.daily_tasks && plan.daily_tasks.length > 0 ? `
        <div class="plan-section">
          <h5 class="section-sub-title">每日任务</h5>
          <div class="daily-tasks-preview">
            ${plan.daily_tasks.slice(0, 3).map(task => `
              <div class="daily-task-item">
                <span class="task-day">${task.day}</span>
                <span class="task-content">${task.content}</span>
                <span class="task-duration">⏱️${task.duration || '30分钟'}</span>
              </div>
            `).join('')}
            ${plan.daily_tasks.length > 3 ? `<div class="more-tasks">还有 ${plan.daily_tasks.length - 3} 个任务...</div>` : ''}
          </div>
        </div>
      ` : ''}

      ${plan.weekly_goals && plan.weekly_goals.length > 0 ? `
        <div class="plan-section">
          <h5 class="section-sub-title">周目标</h5>
          <div class="weekly-goals-preview">
            ${plan.weekly_goals.map(week => `
              <div class="week-item">
                <span class="week-name">${week.week}</span>
                <ul class="week-goals-list">
                  ${(week.goals || []).map(g => `<li>${g}</li>`).join('')}
                </ul>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}

      ${plan.motivation_tips && plan.motivation_tips.length > 0 ? `
        <div class="plan-motivation">
          <span class="motivation-icon">💪</span>
          <span class="motivation-text">${plan.motivation_tips[0]}</span>
        </div>
      ` : ''}
    </div>
  `
}

/**
 * 应用学习计划到学生
 */
export async function applyStudentLearningPlan(studentId) {
  const planContent = document.getElementById('diagnosis-plan-content')
  if (!planContent) return

  const planElement = planContent.querySelector('.learning-plan-preview')
  if (!planElement) {
    Toast.warning('请先生成学习计划')
    return
  }

  showLoading('正在应用学习计划...')

  try {
    const result = await diagnosisService.getStudentLearningPlan(studentId)
    if (!result.success || !result.data) {
      throw new Error('获取学习计划失败')
    }

    const applyResult = await diagnosisService.applyLearningPlan(studentId, result.data)
    if (applyResult.success) {
      Toast.success('学习计划已应用到学生')
      // 更新UI状态
      const btnApply = document.getElementById('btn-apply-plan')
      if (btnApply) {
        btnApply.innerHTML = '<span class="btn-icon">✅</span>已应用'
        btnApply.disabled = true
        btnApply.classList.add('btn-disabled')
      }
    } else {
      throw new Error(applyResult.message || '应用失败')
    }
  } catch (error) {
    Toast.error('应用失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 发送学习计划给家长
 */
export async function sendPlanToParentHandler(studentId) {
  showLoading('正在发送...')

  try {
    const result = await diagnosisService.sendPlanToParent(studentId)
    if (result.success) {
      Toast.success('学习计划已发送给家长')
      const btnSend = document.getElementById('btn-send-plan')
      if (btnSend) {
        btnSend.innerHTML = '<span class="btn-icon">📱</span>已发送'
        btnSend.disabled = true
        btnSend.classList.add('btn-disabled')
      }
    } else {
      throw new Error(result.message || '发送失败')
    }
  } catch (error) {
    Toast.error('发送失败：' + error.message)
  } finally {
    hideLoading()
  }
}

/**
 * 获取障碍类型名称
 */
function getBarrierTypeName(type) {
  const names = {
    concept: '概念理解型',
    reading: '审题障碍型',
    expression: '表述障碍型'
  }
  return names[type] || type
}

/**
 * 获取障碍等级名称
 */
function getBarrierLevelName(level) {
  const names = {
    severe: '严重',
    moderate: '中度',
    mild: '轻度'
  }
  return names[level] || level
}

// 导出全局函数
if (typeof window !== 'undefined') {
  window.saveDiagnosisConfig = saveDiagnosisConfig
  window.loadClassDiagnosis = loadClassDiagnosis
  window.showStudentDiagnosis = showStudentDiagnosis
  window.generateStudentLearningPlan = generateStudentLearningPlan
  window.applyStudentLearningPlan = applyStudentLearningPlan
  window.sendPlanToParentHandler = sendPlanToParentHandler
}
