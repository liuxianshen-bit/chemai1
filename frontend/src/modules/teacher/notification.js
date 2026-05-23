/**
 * 教师端 - 通知管理模块
 */

import { notificationService } from '../../services/notification.js'
import { classService } from '../../services/index.js'
import { Toast, showLoading, hideLoading } from '../../components/index.js'

let currentStep = 1 // 1: 选择类型, 2: 选择对象, 3: 填写内容, 4: 确认发送
let selectedType = ''
let selectedTarget = 'class' // class, student, parent
let selectedClassId = ''
let selectedStudentIds = []
let selectedParentIds = []
let notificationForm = {
  title: '',
  content: '',
  type: 'reminder',
  channel: 'in_app'
}

/**
 * 初始化通知模块
 */
export function initNotificationModule() {
  const container = document.getElementById('notification-send-container')
  if (!container) return

  resetForm()
  renderNotificationSend(container)
}

/**
 * 重置表单
 */
function resetForm() {
  currentStep = 1
  selectedType = ''
  selectedTarget = 'class'
  selectedClassId = ''
  selectedStudentIds = []
  selectedParentIds = []
  notificationForm = {
    title: '',
    content: '',
    type: 'reminder',
    channel: 'in_app'
  }
}

/**
 * 渲染通知发送界面
 */
function renderNotificationSend(container) {
  container.innerHTML = `
    <div class="notification-send">
      <!-- 步骤指示器 -->
      <div class="steps-indicator">
        <div class="step ${currentStep >= 1 ? 'active' : ''} ${currentStep > 1 ? 'completed' : ''}">
          <div class="step-number">1</div>
          <div class="step-label">选择类型</div>
        </div>
        <div class="step-line ${currentStep > 1 ? 'active' : ''}"></div>
        <div class="step ${currentStep >= 2 ? 'active' : ''} ${currentStep > 2 ? 'completed' : ''}">
          <div class="step-number">2</div>
          <div class="step-label">选择对象</div>
        </div>
        <div class="step-line ${currentStep > 2 ? 'active' : ''}"></div>
        <div class="step ${currentStep >= 3 ? 'active' : ''} ${currentStep > 3 ? 'completed' : ''}">
          <div class="step-number">3</div>
          <div class="step-label">填写内容</div>
        </div>
        <div class="step-line ${currentStep > 3 ? 'active' : ''}"></div>
        <div class="step ${currentStep >= 4 ? 'active' : ''}">
          <div class="step-number">4</div>
          <div class="step-label">确认发送</div>
        </div>
      </div>

      <!-- 步骤内容 -->
      <div class="step-content" id="notification-step-content">
        ${renderStepContent()}
      </div>
    </div>

    <style>
      .notification-send {
        max-width: 600px;
        margin: 0 auto;
      }

      .steps-indicator {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 32px;
      }

      .step {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
      }

      .step-number {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--bg-tertiary);
        color: var(--text-muted);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        font-size: 0.875rem;
      }

      .step.active .step-number {
        background: var(--accent);
        color: white;
      }

      .step.completed .step-number {
        background: var(--success);
        color: white;
      }

      .step-label {
        font-size: 0.75rem;
        color: var(--text-muted);
      }

      .step.active .step-label {
        color: var(--accent);
        font-weight: 500;
      }

      .step-line {
        width: 40px;
        height: 2px;
        background: var(--bg-tertiary);
        margin: 0 8px 20px;
      }

      .step-line.active {
        background: var(--accent);
      }

      .step-content {
        background: var(--bg-card);
        border-radius: 12px;
        padding: 24px;
      }

      .type-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
      }

      .type-card {
        padding: 20px;
        border: 2px solid var(--border);
        border-radius: 12px;
        cursor: pointer;
        transition: all 0.2s;
        text-align: center;
      }

      .type-card:hover {
        border-color: var(--accent);
        background: var(--bg-tertiary);
      }

      .type-card.selected {
        border-color: var(--accent);
        background: var(--accent-bg);
      }

      .type-card .icon {
        font-size: 2rem;
        margin-bottom: 8px;
      }

      .type-card .label {
        font-weight: 500;
        color: var(--text-primary);
      }

      .type-card .desc {
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-top: 4px;
      }

      .target-options {
        display: flex;
        gap: 12px;
        margin-bottom: 20px;
      }

      .target-option {
        flex: 1;
        padding: 16px;
        border: 2px solid var(--border);
        border-radius: 12px;
        cursor: pointer;
        text-align: center;
        transition: all 0.2s;
      }

      .target-option:hover {
        border-color: var(--accent);
      }

      .target-option.selected {
        border-color: var(--accent);
        background: var(--accent-bg);
      }

      .form-group {
        margin-bottom: 16px;
      }

      .form-group label {
        display: block;
        font-weight: 500;
        margin-bottom: 8px;
        color: var(--text-primary);
      }

      .form-group input,
      .form-group textarea,
      .form-group select {
        width: 100%;
        padding: 12px;
        border: 1px solid var(--border);
        border-radius: 8px;
        font-size: 0.875rem;
        background: var(--bg);
      }

      .form-group textarea {
        min-height: 120px;
        resize: vertical;
      }

      .channel-options {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }

      .channel-option {
        padding: 8px 16px;
        border: 1px solid var(--border);
        border-radius: 20px;
        cursor: pointer;
        font-size: 0.875rem;
        transition: all 0.2s;
      }

      .channel-option:hover {
        border-color: var(--accent);
      }

      .channel-option.selected {
        border-color: var(--accent);
        background: var(--accent);
        color: white;
      }

      .btn-group {
        display: flex;
        gap: 12px;
        margin-top: 24px;
      }

      .student-list,
      .class-list {
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid var(--border);
        border-radius: 8px;
      }

      .student-item,
      .class-item {
        padding: 12px;
        border-bottom: 1px solid var(--border);
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .student-item:last-child,
      .class-item:last-child {
        border-bottom: none;
      }

      .student-item:hover,
      .class-item:hover {
        background: var(--bg-tertiary);
      }

      .student-item.selected,
      .class-item.selected {
        background: var(--accent-bg);
      }

      .summary-card {
        background: var(--bg-tertiary);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
      }

      .summary-card .row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid var(--border);
      }

      .summary-card .row:last-child {
        border-bottom: none;
      }

      .summary-card .label {
        color: var(--text-muted);
      }

      .summary-card .value {
        font-weight: 500;
        color: var(--text-primary);
      }
    </style>
  `
}

/**
 * 渲染步骤内容
 */
function renderStepContent() {
  switch (currentStep) {
    case 1:
      return renderStep1_TypeSelect()
    case 2:
      return renderStep2_TargetSelect()
    case 3:
      return renderStep3_ContentFill()
    case 4:
      return renderStep4_Confirm()
    default:
      return ''
  }
}

/**
 * 步骤1: 选择通知类型
 */
function renderStep1_TypeSelect() {
  return `
    <h3 style="margin-bottom: 20px;">选择通知类型</h3>
    <div class="type-grid">
      <div class="type-card ${selectedType === 'daily_report' ? 'selected' : ''}" onclick="teacherNotificationModule.selectType('daily_report')">
        <div class="icon">📊</div>
        <div class="label">日常报告</div>
        <div class="desc">每日学习情况汇总</div>
      </div>
      <div class="type-card ${selectedType === 'weekly_report' ? 'selected' : ''}" onclick="teacherNotificationModule.selectType('weekly_report')">
        <div class="icon">📈</div>
        <div class="label">周报</div>
        <div class="desc">每周学习情况汇总</div>
      </div>
      <div class="type-card ${selectedType === 'score_alert' ? 'selected' : ''}" onclick="teacherNotificationModule.selectType('score_alert')">
        <div class="icon">⚠️</div>
        <div class="label">成绩预警</div>
        <div class="desc">成绩异常下降提醒</div>
      </div>
      <div class="type-card ${selectedType === 'warning' ? 'selected' : ''}" onclick="teacherNotificationModule.selectType('warning')">
        <div class="icon">🔴</div>
        <div class="label">学情预警</div>
        <div class="desc">学习异常预警通知</div>
      </div>
      <div class="type-card ${selectedType === 'reminder' ? 'selected' : ''}" onclick="teacherNotificationModule.selectType('reminder')">
        <div class="icon">⏰</div>
        <div class="label">复习提醒</div>
        <div class="desc">复习任务到期提醒</div>
      </div>
      <div class="type-card ${selectedType === 'custom' ? 'selected' : ''}" onclick="teacherNotificationModule.selectType('custom')">
        <div class="icon">📝</div>
        <div class="label">自定义</div>
        <div class="desc">发送自定义通知</div>
      </div>
    </div>
    <div class="btn-group">
      <button class="btn-primary" onclick="teacherNotificationModule.nextStep()" ${!selectedType ? 'disabled' : ''}>
        下一步
      </button>
    </div>
  `
}

/**
 * 步骤2: 选择发送对象
 */
function renderStep2_TargetSelect() {
  return `
    <h3 style="margin-bottom: 20px;">选择发送对象</h3>

    <div class="target-options">
      <div class="target-option ${selectedTarget === 'class' ? 'selected' : ''}" onclick="teacherNotificationModule.selectTarget('class')">
        <div style="font-size: 1.5rem; margin-bottom: 4px;">👥</div>
        <div>全班</div>
      </div>
      <div class="target-option ${selectedTarget === 'student' ? 'selected' : ''}" onclick="teacherNotificationModule.selectTarget('student')">
        <div style="font-size: 1.5rem; margin-bottom: 4px;">👤</div>
        <div>指定学生</div>
      </div>
      <div class="target-option ${selectedTarget === 'parent' ? 'selected' : ''}" onclick="teacherNotificationModule.selectTarget('parent')">
        <div style="font-size: 1.5rem; margin-bottom: 4px;">👨‍👩‍👧</div>
        <div>家长</div>
      </div>
    </div>

    <div id="target-selection-area">
      ${renderTargetSelection()}
    </div>

    <div class="btn-group">
      <button class="btn-secondary" onclick="teacherNotificationModule.prevStep()">上一步</button>
      <button class="btn-primary" onclick="teacherNotificationModule.nextStep()">
        下一步
      </button>
    </div>
  `
}

/**
 * 渲染目标选择区
 */
function renderTargetSelection() {
  if (selectedTarget === 'class') {
    return `
      <div class="form-group">
        <label>选择班级</label>
        <select id="target-class-select" onchange="teacherNotificationModule.selectClass(this.value)">
          <option value="">请选择班级...</option>
        </select>
      </div>
    `
  } else if (selectedTarget === 'student') {
    return `
      <div class="form-group">
        <label>选择学生（可多选）</label>
        <div class="student-list" id="student-select-list">
          <div style="padding: 20px; text-align: center; color: var(--text-muted);">请先选择一个班级</div>
        </div>
      </div>
    `
  } else if (selectedTarget === 'parent') {
    return `
      <div class="form-group">
        <label>选择家长（可多选）</label>
        <div class="student-list" id="parent-select-list">
          <div style="padding: 20px; text-align: center; color: var(--text-muted);">请先选择一个班级</div>
        </div>
      </div>
    `
  }
  return ''
}

/**
 * 步骤3: 填写内容
 */
function renderStep3_ContentFill() {
  return `
    <h3 style="margin-bottom: 20px;">填写通知内容</h3>

    <div class="form-group">
      <label>通知标题</label>
      <input type="text" id="notification-title" placeholder="请输入通知标题"
             value="${notificationForm.title}"
             oninput="teacherNotificationModule.updateForm('title', this.value)">
    </div>

    <div class="form-group">
      <label>通知内容</label>
      <textarea id="notification-content" placeholder="请输入通知内容"
                oninput="teacherNotificationModule.updateForm('content', this.value)">${notificationForm.content}</textarea>
    </div>

    <div class="form-group">
      <label>发送渠道</label>
      <div class="channel-options">
        <div class="channel-option ${notificationForm.channel === 'in_app' ? 'selected' : ''}"
             onclick="teacherNotificationModule.selectChannel('in_app')">
          📱 App通知
        </div>
        <div class="channel-option ${notificationForm.channel === 'telegram' ? 'selected' : ''}"
             onclick="teacherNotificationModule.selectChannel('telegram')">
          ✈️ Telegram
        </div>
        <div class="channel-option ${notificationForm.channel === 'email' ? 'selected' : ''}"
             onclick="teacherNotificationModule.selectChannel('email')">
          📧 邮件
        </div>
      </div>
    </div>

    <div class="btn-group">
      <button class="btn-secondary" onclick="teacherNotificationModule.prevStep()">上一步</button>
      <button class="btn-primary" onclick="teacherNotificationModule.nextStep()"
              ${!notificationForm.title || !notificationForm.content ? 'disabled' : ''}>
        下一步
      </button>
    </div>
  `
}

/**
 * 步骤4: 确认发送
 */
function renderStep4_Confirm() {
  const typeNames = {
    'daily_report': '日常报告',
    'weekly_report': '周报',
    'score_alert': '成绩预警',
    'warning': '学情预警',
    'reminder': '复习提醒',
    'custom': '自定义'
  }

  const targetNames = {
    'class': '全班',
    'student': `学生 (${selectedStudentIds.length}人)`,
    'parent': `家长 (${selectedParentIds.length}人)`
  }

  return `
    <h3 style="margin-bottom: 20px;">确认发送</h3>

    <div class="summary-card">
      <div class="row">
        <span class="label">通知类型</span>
        <span class="value">${typeNames[selectedType] || selectedType}</span>
      </div>
      <div class="row">
        <span class="label">发送对象</span>
        <span class="value">${targetNames[selectedTarget]}</span>
      </div>
      <div class="row">
        <span class="label">发送渠道</span>
        <span class="value">${notificationForm.channel === 'in_app' ? 'App通知' : notificationForm.channel}</span>
      </div>
      <div class="row">
        <span class="label">通知标题</span>
        <span class="value">${notificationForm.title}</span>
      </div>
    </div>

    <div style="background: var(--bg-tertiary); border-radius: 8px; padding: 16px; margin-bottom: 16px;">
      <div style="font-weight: 500; margin-bottom: 8px;">通知内容：</div>
      <div style="color: var(--text-secondary);">${notificationForm.content}</div>
    </div>

    <div class="btn-group">
      <button class="btn-secondary" onclick="teacherNotificationModule.prevStep()">上一步</button>
      <button class="btn-primary" onclick="teacherNotificationModule.sendNotification()">
        确认发送
      </button>
    </div>
  `
}

/**
 * 选择通知类型
 */
export function selectType(type) {
  selectedType = type
  notificationForm.type = type
  const container = document.getElementById('notification-step-content')
  if (container) {
    container.innerHTML = renderStepContent()
  }
  loadClassListForTarget()
}

/**
 * 选择目标类型
 */
export function selectTarget(target) {
  selectedTarget = target
  selectedStudentIds = []
  selectedParentIds = []
  const container = document.getElementById('notification-step-content')
  if (container) {
    container.innerHTML = renderStepContent()
  }
  loadClassListForTarget()
}

/**
 * 选择班级
 */
export function selectClass(classId) {
  selectedClassId = classId
  loadStudentsForClass(classId)
}

/**
 * 加载班级列表
 */
async function loadClassListForTarget() {
  if (selectedTarget === 'class' || selectedTarget === 'student' || selectedTarget === 'parent') {
    const select = document.getElementById('target-class-select')
    if (select) {
      showLoading('加载班级...')
      try {
        const result = await classService.getClassList()
        if (result.success) {
          const classes = result.data || []
          select.innerHTML = '<option value="">请选择班级...</option>' +
            classes.map(c => `<option value="${c.id || c.class_id}">${c.name}</option>`).join('')

          // 如果已有selectedClassId，设置选中
          if (selectedClassId) {
            select.value = selectedClassId
            loadStudentsForClass(selectedClassId)
          }
        }
      } catch (e) {
        console.error('加载班级失败', e)
      } finally {
        hideLoading()
      }
    }
  }
}

/**
 * 加载班级学生
 */
async function loadStudentsForClass(classId) {
  if (!classId) return

  const studentList = document.getElementById('student-select-list')
  const parentList = document.getElementById('parent-select-list')

  showLoading('加载学生...')
  try {
    const result = await classService.getClassStudents(classId)
    if (result.success) {
      const students = result.data || []

      if (studentList) {
        if (students.length === 0) {
          studentList.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">该班级暂无学生</div>'
        } else {
          studentList.innerHTML = students.map(s => `
            <div class="student-item ${selectedStudentIds.includes(s.student_id) ? 'selected' : ''}"
                 onclick="teacherNotificationModule.toggleStudent('${s.student_id}')">
              <input type="checkbox" ${selectedStudentIds.includes(s.student_id) ? 'checked' : ''}>
              <span>${s.name || s.student_name}</span>
              <span style="color: var(--text-muted); font-size: 0.75rem;">${s.student_id}</span>
            </div>
          `).join('')
        }
      }

      if (parentList) {
        // 家长列表暂时用学生代替，实际应从API获取
        parentList.innerHTML = students.map(s => `
          <div class="student-item ${selectedParentIds.includes(s.student_id) ? 'selected' : ''}"
               onclick="teacherNotificationModule.toggleParent('${s.student_id}')">
            <input type="checkbox" ${selectedParentIds.includes(s.student_id) ? 'checked' : ''}>
            <span>${s.name || s.student_name} 的家长</span>
          </div>
        `).join('')
      }
    }
  } catch (e) {
    console.error('加载学生失败', e)
  } finally {
    hideLoading()
  }
}

/**
 * 切换学生选择
 */
export function toggleStudent(studentId) {
  const idx = selectedStudentIds.indexOf(studentId)
  if (idx === -1) {
    selectedStudentIds.push(studentId)
  } else {
    selectedStudentIds.splice(idx, 1)
  }
  const container = document.getElementById('notification-step-content')
  if (container) {
    container.innerHTML = renderStepContent()
  }
}

/**
 * 切换家长选择
 */
export function toggleParent(parentId) {
  const idx = selectedParentIds.indexOf(parentId)
  if (idx === -1) {
    selectedParentIds.push(parentId)
  } else {
    selectedParentIds.splice(idx, 1)
  }
  const container = document.getElementById('notification-step-content')
  if (container) {
    container.innerHTML = renderStepContent()
  }
}

/**
 * 更新表单
 */
export function updateForm(field, value) {
  notificationForm[field] = value
}

/**
 * 选择渠道
 */
export function selectChannel(channel) {
  notificationForm.channel = channel
  const container = document.getElementById('notification-step-content')
  if (container) {
    container.innerHTML = renderStepContent()
  }
}

/**
 * 下一步
 */
export function nextStep() {
  if (currentStep < 4) {
    currentStep++
    const container = document.getElementById('notification-step-content')
    if (container) {
      container.innerHTML = renderStepContent()
      if (currentStep === 2) {
        loadClassListForTarget()
      }
    }
  }
}

/**
 * 上一步
 */
export function prevStep() {
  if (currentStep > 1) {
    currentStep--
    const container = document.getElementById('notification-step-content')
    if (container) {
      container.innerHTML = renderStepContent()
      if (currentStep === 2) {
        loadClassListForTarget()
      }
    }
  }
}

/**
 * 发送通知
 */
export async function sendNotification() {
  showLoading('发送中...')
  try {
    let result
    if (selectedTarget === 'class') {
      result = await notificationService.sendToClass(
        selectedClassId,
        notificationForm.type,
        notificationForm.title,
        notificationForm.content,
        'students'
      )
    } else if (selectedTarget === 'student') {
      // 逐个发送
      for (const studentId of selectedStudentIds) {
        result = await notificationService.sendToStudent(
          studentId,
          notificationForm.type,
          notificationForm.title,
          notificationForm.content
        )
      }
    } else if (selectedTarget === 'parent') {
      // 逐个发送
      for (const studentId of selectedParentIds) {
        result = await notificationService.sendToParent(
          studentId,
          notificationForm.type,
          notificationForm.title,
          notificationForm.content
        )
      }
    }

    if (result?.success || result?.notification_id) {
      Toast.success('通知发送成功')
      resetForm()
      const container = document.getElementById('notification-send-container')
      if (container) {
        renderNotificationSend(container)
      }
    } else {
      Toast.error(result?.message || '发送失败')
    }
  } catch (e) {
    Toast.error('发送失败：' + e.message)
  } finally {
    hideLoading()
  }
}

// 导出给window调用
if (typeof window !== 'undefined') {
  window.teacherNotificationModule = {
    init: initNotificationModule,
    selectType,
    selectTarget,
    selectClass,
    toggleStudent,
    toggleParent,
    updateForm,
    selectChannel,
    nextStep,
    prevStep,
    sendNotification
  }
}

export default {
  init: initNotificationModule,
  selectType,
  selectTarget,
  selectClass,
  toggleStudent,
  toggleParent,
  updateForm,
  selectChannel,
  nextStep,
  prevStep,
  sendNotification
}
