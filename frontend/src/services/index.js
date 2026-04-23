/**
 * 服务层统一导出
 */

// API核心
export { api, handleApiError, ApiError, addRequestInterceptor, addResponseInterceptor } from './api.js'

// 认证服务
export { authService, UserStatus, UserRole } from './auth.js'

// Hermes Agent 服务
export { hermesService, HermesEventType, ConfirmType, TaskType } from './hermes.js'

// 业务服务
export { examService } from './exam.js'
export { questionService } from './question.js'
export { diagnosisService, BarrierType, BarrierLevel, BarrierTypeNames, BarrierLevelNames } from './diagnosis.js'
export { practiceService, PracticeStatus, PracticeStatusNames } from './practice.js'
export { reportService } from './report.js'
export { userService, permissionService, classService } from './user.js'
export { schoolService, gradeService, teacherAppService } from './school.js'
