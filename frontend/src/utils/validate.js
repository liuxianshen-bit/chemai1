/**
 * 验证工具 - Validation Utils
 */

// ============================================
// 常用验证规则
// ============================================

export const Rules = {
  required: (msg = '此字段必填') => ({
    validate: (value) => value !== null && value !== undefined && String(value).trim() !== '',
    message: msg
  }),

  minLength: (min, msg) => ({
    validate: (value) => value && String(value).length >= min,
    message: msg || `长度不能少于${min}个字符`
  }),

  maxLength: (max, msg) => ({
    validate: (value) => !value || String(value).length <= max,
    message: msg || `长度不能超过${max}个字符`
  }),

  email: (msg = '请输入有效的邮箱地址') => ({
    validate: (value) => !value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
    message: msg
  }),

  phone: (msg = '请输入有效的手机号码') => ({
    validate: (value) => !value || /^1[3-9]\d{9}$/.test(value),
    message: msg
  }),

  url: (msg = '请输入有效的网址') => ({
    validate: (value) => !value || /^https?:\/\/.+/.test(value),
    message: msg
  }),

  positiveInteger: (msg = '请输入正整数') => ({
    validate: (value) => !value || /^[1-9]\d*$/.test(value),
    message: msg
  }),

  range: (min, max, msg) => ({
    validate: (value) => {
      const num = Number(value)
      return !isNaN(num) && num >= min && num <= max
    },
    message: msg || `数值必须在${min}到${max}之间`
  }),

  pattern: (regex, msg) => ({
    validate: (value) => !value || regex.test(value),
    message: msg || '格式不正确'
  })
}

// ============================================
// 验证器类
// ============================================

export class Validator {
  constructor() {
    this.rules = []
    this.errors = []
  }

  add(field, ...ruleFactories) {
    for (const factory of ruleFactories) {
      this.rules.push({ field, ...factory })
    }
    return this
  }

  required(field, msg) {
    return this.add(field, Rules.required(msg))
  }

  email(field) {
    return this.add(field, Rules.email())
  }

  phone(field) {
    return this.add(field, Rules.phone())
  }

  minLength(field, min, msg) {
    return this.add(field, Rules.minLength(min, msg))
  }

  maxLength(field, max, msg) {
    return this.add(field, Rules.maxLength(max, msg))
  }

  range(field, min, max, msg) {
    return this.add(field, Rules.range(min, max, msg))
  }

  pattern(field, regex, msg) {
    return this.add(field, Rules.pattern(regex, msg))
  }

  validate(data) {
    this.errors = []

    for (const rule of this.rules) {
      const value = data[rule.field]
      if (!rule.validate(value)) {
        this.errors.push({
          field: rule.field,
          message: rule.message
        })
      }
    }

    return this.errors.length === 0
  }

  getErrors() {
    return this.errors
  }

  getError(field) {
    return this.errors.find(e => e.field === field)?.message
  }
}

// ============================================
// 快捷验证函数
// ============================================

export function validate(data, schema) {
  const validator = new Validator()

  for (const [field, rules] of Object.entries(schema)) {
    for (const rule of rules) {
      validator.add(field, rule)
    }
  }

  return {
    valid: validator.validate(data),
    errors: validator.getErrors()
  }
}
