/**
 * 管理模块 - 学校/年级/教师入驻
 */
import { schoolService, gradeService, teacherAppService, userService } from '../../services/index.js'
import { classService } from '../../services/index.js'
import { Toast } from '../../components/index.js'

// ============================================
// 学校设置模块
// ============================================
export function initSchoolModule() {
  loadSchoolInfo()
}

async function loadSchoolInfo() {
  try {
    const result = await schoolService.getSchool()
    if (result.success) {
      renderSchoolInfo(result.school)
    }
  } catch (error) {
    console.error('加载学校信息失败:', error)
  }
}

function renderSchoolInfo(school) {
  const container = document.getElementById('school-info')
  if (!container) return
  container.innerHTML = `
    <div class="info-item">
      <label>学校名称</label>
      <span>${school.name || '-'}</span>
    </div>
    <div class="info-item">
      <label>地区</label>
      <span>${school.region || '-'}</span>
    </div>
    <div class="info-item">
      <label>地址</label>
      <span>${school.address || '-'}</span>
    </div>
    <div class="info-item">
      <label>电话</label>
      <span>${school.phone || '-'}</span>
    </div>
    <div class="info-item">
      <label>当前学期</label>
      <span>${school.current_term || '-'}</span>
    </div>
    <div class="info-item">
      <label>科目</label>
      <span>${(school.subjects || []).join(', ') || '-'}</span>
    </div>
  `
}

// ============================================
// 年级管理模块
// ============================================
export function initGradeModule() {
  loadGrades()
}

async function loadGrades() {
  try {
    const result = await gradeService.getGrades()
    if (result.success) {
      renderGrades(result.grades)
    }
  } catch (error) {
    console.error('加载年级列表失败:', error)
  }
}

function renderGrades(grades) {
  const container = document.getElementById('grade-list')
  if (!container) return

  if (grades.length === 0) {
    container.innerHTML = '<p class="empty-tip">暂无年级数据</p>'
    return
  }

  container.innerHTML = grades.map(grade => `
    <div class="grade-card">
      <div class="grade-name">${grade.name}</div>
      <div class="grade-year">${grade.year}年</div>
      <div class="grade-status">${grade.status === 1 ? '在读' : '已毕业'}</div>
    </div>
  `).join('')
}

// ============================================
// 教师入驻审批模块
// ============================================
export function initTeacherAppModule() {
  loadTeacherApplications()
}

async function loadTeacherApplications() {
  try {
    const result = await teacherAppService.getApplications()
    if (result.success) {
      renderTeacherApplications(result.applications)
    }
  } catch (error) {
    console.error('加载教师申请列表失败:', error)
  }
}

async function handleApproveApplication(appId) {
  try {
    const result = await teacherAppService.approveApplication(appId)
    if (result.success) {
      Toast.success('审批通过，已创建教师账号')
      loadTeacherApplications() // 刷新列表
    } else {
      Toast.error(result.message || '操作失败')
    }
  } catch (error) {
    Toast.error('操作失败: ' + error.message)
  }
}

async function handleRejectApplication(appId) {
  try {
    const result = await teacherAppService.rejectApplication(appId)
    if (result.success) {
      Toast.success('已拒绝申请')
      loadTeacherApplications() // 刷新列表
    } else {
      Toast.error(result.message || '操作失败')
    }
  } catch (error) {
    Toast.error('操作失败: ' + error.message)
  }
}

function renderTeacherApplications(applications) {
  const container = document.getElementById('teacher-app-list')
  if (!container) return

  if (applications.length === 0) {
    container.innerHTML = '<p class="empty-tip">暂无待审批申请</p>'
    return
  }

  container.innerHTML = applications.map(app => `
    <div class="app-card">
      <div class="app-info">
        <div class="app-name">${app.name}</div>
        <div class="app-detail">手机: ${app.phone}</div>
        <div class="app-detail">学校: ${app.school}</div>
        <div class="app-detail">科目: ${app.subject}</div>
      </div>
      <div class="app-actions">
        <button class="btn-approve" onclick="handleApproveApplication('${app.id}')">通过</button>
        <button class="btn-reject" onclick="handleRejectApplication('${app.id}')">拒绝</button>
      </div>
    </div>
  `).join('')

  // 暴露到全局供按钮调用
  window.handleApproveApplication = handleApproveApplication
  window.handleRejectApplication = handleRejectApplication
}

// ============================================
// 班级管理模块
// ============================================
export function initClassModule() {
  loadClasses()
}

async function loadClasses() {
  try {
    const result = await classService.getClassList()
    if (result.success) {
      renderClasses(result.classes || [])
    }
  } catch (error) {
    console.error('加载班级列表失败:', error)
  }
}

function renderClasses(classes) {
  const container = document.getElementById('class-list')
  if (!container) return

  if (classes.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🏠</div><p>暂无班级数据</p></div>'
    return
  }

  container.innerHTML = `
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="border-bottom:1px solid var(--border);">
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">班级名称</th>
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">年级</th>
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">班主任</th>
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">学生数</th>
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">操作</th>
        </tr>
      </thead>
      <tbody>
        ${classes.map(c => `
          <tr style="border-bottom:1px solid var(--border-subtle);">
            <td style="padding:12px 16px;">${c.name}</td>
            <td style="padding:12px 16px;">${c.grade || '-'}</td>
            <td style="padding:12px 16px;">${c.teacher_name || '-'}</td>
            <td style="padding:12px 16px;">${c.student_count || 0}</td>
            <td style="padding:12px 16px;">
              <button class="btn-secondary btn-sm" onclick="editClass('${c.class_id}')">编辑</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `
}

// ============================================
// 教师管理模块
// ============================================
export function initTeacherManagementModule() {
  loadTeachers()
}

async function loadTeachers() {
  try {
    const result = await userService.getTeacherList()
    if (result.success) {
      renderTeachers(result.teachers || [])
    }
  } catch (error) {
    console.error('加载教师列表失败:', error)
  }
}

function renderTeachers(teachers) {
  const container = document.getElementById('teacher-list')
  if (!container) return

  if (teachers.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">👨‍🏫</div><p>暂无教师数据</p></div>'
    return
  }

  container.innerHTML = `
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="border-bottom:1px solid var(--border);">
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">姓名</th>
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">角色</th>
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">手机</th>
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">任教班级</th>
          <th style="text-align:left;padding:12px 16px;font-size:0.75rem;color:var(--text-muted);">操作</th>
        </tr>
      </thead>
      <tbody>
        ${teachers.map(t => `
          <tr style="border-bottom:1px solid var(--border-subtle);">
            <td style="padding:12px 16px;">${t.name}</td>
            <td style="padding:12px 16px;">${t.role || '教师'}</td>
            <td style="padding:12px 16px;">${t.phone || '-'}</td>
            <td style="padding:12px 16px;">-</td>
            <td style="padding:12px 16px;">
              <button class="btn-secondary btn-sm" onclick="assignTeacherClasses('${t.teacher_id}')">分配班级</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `
}

// ============================================
// 暴露全局函数
// ============================================
window.loadSchoolInfo = loadSchoolInfo
window.loadGrades = loadGrades
window.loadClasses = loadClasses
window.loadTeachers = loadTeachers
window.loadTeacherApplications = loadTeacherApplications
window.showAddGradeModal = showAddGradeModal
window.showAddClassModal = showAddClassModal

// ============================================
// 添加年级弹窗
// ============================================
function showAddGradeModal() {
  const modal = document.getElementById('modal-add-grade') || createModal('modal-add-grade', '添加年级', `
    <div style="padding:16px;">
      <div style="margin-bottom:12px;">
        <label style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:4px;">年级名称</label>
        <input type="text" id="grade-name-input" placeholder="如：高一" style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:6px;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:4px;">年份</label>
        <input type="number" id="grade-year-input" value="2026" style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:6px;">
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
        <button class="btn-secondary" onclick="closeModal('modal-add-grade')">取消</button>
        <button class="btn-primary" onclick="handleAddGrade()">确定</button>
      </div>
    </div>
  `)
  modal.style.display = 'flex'
}

async function handleAddGrade() {
  const name = document.getElementById('grade-name-input')?.value?.trim()
  const year = parseInt(document.getElementById('grade-year-input')?.value) || 2026

  if (!name) {
    Toast.error('请输入年级名称')
    return
  }

  try {
    const result = await gradeService.createGrade({ name, year })
    if (result.success) {
      Toast.success('年级创建成功')
      closeModal('modal-add-grade')
      loadGrades()
    } else {
      Toast.error(result.message || '创建失败')
    }
  } catch (error) {
    Toast.error('创建失败：' + error.message)
  }
}

function closeModal(id) {
  const modal = document.getElementById(id)
  if (modal) modal.style.display = 'none'
}

function createModal(id, title, content) {
  const existing = document.getElementById(id)
  if (existing) return existing

  const modal = document.createElement('div')
  modal.id = id
  modal.style.cssText = 'position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,0.5);z-index:1000;'
  modal.innerHTML = `
    <div style="background:white;border-radius:12px;min-width:360px;max-width:480px;box-shadow:var(--shadow-lg);">
      <div style="padding:16px 20px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;">
        <h3 style="font-size:1rem;font-weight:600;">${title}</h3>
        <button onclick="closeModal('${id}')" style="background:none;border:none;font-size:1.25rem;cursor:pointer;padding:4px;line-height:1;">&times;</button>
      </div>
      ${content}
    </div>
  `
  document.body.appendChild(modal)
  return modal
}

window.closeModal = closeModal

// ============================================
// 添加班级弹窗
// ============================================
async function showAddClassModal() {
  // 先获取年级列表
  const gradesResult = await gradeService.getGrades()
  const grades = gradesResult.success ? gradesResult.grades : []

  const gradesOptions = grades.map(g => `<option value="${g.grade_id}">${g.name}</option>`).join('')

  const modal = document.getElementById('modal-add-class') || createModal('modal-add-class', '添加班级', `
    <div style="padding:16px;">
      <div style="margin-bottom:12px;">
        <label style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:4px;">班级名称</label>
        <input type="text" id="class-name-input" placeholder="如：高一(1)班" style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:6px;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:4px;">所属年级</label>
        <select id="class-grade-input" style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:6px;">
          <option value="">请选择年级</option>
          ${gradesOptions}
        </select>
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
        <button class="btn-secondary" onclick="closeModal('modal-add-class')">取消</button>
        <button class="btn-primary" onclick="handleAddClass()">确定</button>
      </div>
    </div>
  `)
  modal.style.display = 'flex'
}

async function handleAddClass() {
  const name = document.getElementById('class-name-input')?.value?.trim()
  const gradeId = document.getElementById('class-grade-input')?.value

  if (!name) {
    Toast.error('请输入班级名称')
    return
  }
  if (!gradeId) {
    Toast.error('请选择所属年级')
    return
  }

  try {
    const result = await classService.createClass({ name, grade_id: gradeId })
    if (result.success) {
      Toast.success('班级创建成功')
      closeModal('modal-add-class')
      loadClasses()
    } else {
      Toast.error(result.message || '创建失败')
    }
  } catch (error) {
    Toast.error('创建失败：' + error.message)
  }
}

// ============================================
// 初始化管理模块
// ============================================
export function initAdminModule() {
  const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
  if (user.role !== 'admin') {
    console.warn('非管理员，跳过管理模块初始化')
    return
  }
  initSchoolModule()
  initGradeModule()
  initTeacherAppModule()
}
