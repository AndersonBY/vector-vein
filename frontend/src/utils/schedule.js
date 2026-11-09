export const MINUTE_INTERVAL_CHOICES = Object.freeze([1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30])
export const HOUR_INTERVAL_CHOICES = Object.freeze([1, 2, 3, 4, 6, 8, 12])
export const WEEKDAY_ORDER = Object.freeze([1, 2, 3, 4, 5, 6, 0])

export const CALENDAR_INTERVAL_LIMITS = Object.freeze({
  day: { min: 1, max: 365 },
  week: { min: 1, max: 52 },
  month: { min: 1, max: 12 },
})

const DOW_ALIASES = Object.freeze({
  SUN: 0,
  MON: 1,
  TUE: 2,
  WED: 3,
  THU: 4,
  FRI: 5,
  SAT: 6,
})

const MONTH_ALIASES = Object.freeze({
  JAN: 1,
  FEB: 2,
  MAR: 3,
  APR: 4,
  MAY: 5,
  JUN: 6,
  JUL: 7,
  AUG: 8,
  SEP: 9,
  OCT: 10,
  NOV: 11,
  DEC: 12,
})

export const DEFAULT_TIMEZONES = Object.freeze([
  'Asia/Shanghai',
  'UTC',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Asia/Hong_Kong',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
])

export function getLocalTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

export function getTodayLocalDateString(now = new Date()) {
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function parseAnchorDate(dateStr) {
  if (typeof dateStr !== 'string') return null
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr)
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > 31) return null
  const d = new Date(0)
  d.setUTCFullYear(year, month - 1, day)
  if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) {
    return null
  }
  return { year, month, day, utcMs: d.getTime(), dow: d.getUTCDay() }
}

export function isValidAnchorDate(dateStr) {
  return parseAnchorDate(dateStr) !== null
}

export function validateRecurrence(recurrence) {
  if (recurrence === null || recurrence === undefined) {
    return { valid: true, normalized: null }
  }
  if (
    typeof recurrence !== 'object' || Array.isArray(recurrence) ||
    Object.keys(recurrence).length !== 3 ||
    !['unit', 'interval', 'anchor_date'].every(key => Object.hasOwn(recurrence, key))
  ) {
    return { valid: false, error: 'error_schedule_invalid' }
  }
  const { unit, interval, anchor_date } = recurrence
  const limits = CALENDAR_INTERVAL_LIMITS[unit]
  if (!limits) {
    return { valid: false, error: 'error_schedule_invalid' }
  }
  if (!Number.isInteger(interval) || interval < limits.min || interval > limits.max) {
    return { valid: false, error: 'error_interval_invalid', min: limits.min, max: limits.max }
  }
  if (!isValidAnchorDate(anchor_date)) {
    return { valid: false, error: 'error_anchor_date_required' }
  }
  return {
    valid: true,
    normalized: {
      unit,
      interval,
      anchor_date: anchor_date.trim(),
    },
  }
}

export function isValidTimeString(timeStr) {
  if (typeof timeStr !== 'string') return false
  const match = /^(\d{2}):(\d{2})$/.exec(timeStr.trim())
  if (!match) return false
  const hour = Number(match[1])
  const minute = Number(match[2])
  return hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59
}

export function formatTimeHHmm(hour, minute) {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function parseCronTokenValue(raw, min, max, aliases = null) {
  const upper = raw.toUpperCase()
  if (aliases && Object.hasOwn(aliases, upper)) {
    return aliases[upper]
  }
  if (!/^\d+$/.test(raw)) return null
  const num = Number(raw)
  if (!Number.isInteger(num) || num < min || num > max) return null
  return num
}

function validateCronField(field, min, max, aliases = null) {
  if (!field || typeof field !== 'string') return false
  const parts = field.split(',')
  for (const part of parts) {
    if (!part) return false
    const slashParts = part.split('/')
    if (slashParts.length > 2) return false
    const [rangePart, stepPart] = slashParts
    if (stepPart !== undefined) {
      if (!/^\d+$/.test(stepPart)) return false
      if (!/[1-9]/.test(stepPart)) return false
    }
    if (rangePart === '*') continue
    const dashParts = rangePart.split('-')
    if (dashParts.length === 1) {
      if (parseCronTokenValue(dashParts[0], min, max, aliases) === null) return false
    } else if (dashParts.length === 2) {
      const start = parseCronTokenValue(dashParts[0], min, max, aliases)
      const end = parseCronTokenValue(dashParts[1], min, max, aliases)
      if (start === null || end === null) return false
      if (start > end) return false
    } else {
      return false
    }
  }
  return true
}

export function isValidFiveFieldCron(cronExpression) {
  if (typeof cronExpression !== 'string') return false
  const trimmed = cronExpression.trim()
  if (!trimmed) return false
  const fields = trimmed.split(/\s+/)
  if (fields.length !== 5) return false
  const [minField, hourField, domField, monthField, dowField] = fields
  return (
    validateCronField(minField, 0, 59) &&
    validateCronField(hourField, 0, 23) &&
    validateCronField(domField, 1, 31) &&
    validateCronField(monthField, 1, 12, MONTH_ALIASES) &&
    validateCronField(dowField, 0, 7, DOW_ALIASES)
  )
}

export function parseDowField(dowField) {
  if (typeof dowField !== 'string' || !dowField.trim()) return null
  if (dowField === '*') return [...WEEKDAY_ORDER]
  const set = new Set()
  const parts = dowField.split(',')
  for (const part of parts) {
    if (!part || part.includes('/')) return null
    const dashParts = part.split('-')
    if (dashParts.length === 1) {
      const v = parseCronTokenValue(dashParts[0], 0, 7, DOW_ALIASES)
      if (v === null) return null
      set.add(v === 7 ? 0 : v)
    } else if (dashParts.length === 2) {
      const start = parseCronTokenValue(dashParts[0], 0, 7, DOW_ALIASES)
      const end = parseCronTokenValue(dashParts[1], 0, 7, DOW_ALIASES)
      if (start === null || end === null) return null
      if (start > end) return null
      for (let d = start; d <= end; d++) set.add(d === 7 ? 0 : d)
    } else {
      return null
    }
  }
  if (set.size === 0) return null
  return WEEKDAY_ORDER.filter(d => set.has(d))
}

export function serializeWeekdays(weekdays) {
  if (!Array.isArray(weekdays) || weekdays.length === 0) return null
  const unique = WEEKDAY_ORDER.filter(d => weekdays.includes(d))
  if (unique.length === 0) return null
  if (unique.length === 5 && unique.every((d, idx) => d === idx + 1)) {
    return '1-5'
  }
  return unique.join(',')
}

function parseSingleInt(field, min, max) {
  if (!/^\d+$/.test(field)) return null
  const n = Number(field)
  return Number.isInteger(n) && n >= min && n <= max ? n : null
}

export function parseSchedule(cronExpression, recurrence = null) {
  const rawCron = typeof cronExpression === 'string' ? cronExpression.trim() : ''
  const recValidation = validateRecurrence(recurrence)
  if (!recValidation.valid) {
    return {
      valid: false,
      mode: 'custom',
      error: recValidation.error,
      rawCron,
    }
  }
  const normRec = recValidation.normalized

  if (!isValidFiveFieldCron(rawCron)) {
    return {
      valid: false,
      mode: 'custom',
      error: 'error_schedule_invalid',
      rawCron,
    }
  }

  const [minField, hourField, domField, monthField, dowField] = rawCron.split(/\s+/)

  // 1. Minute interval: * * * * * or */N * * * *
  if (!normRec && hourField === '*' && domField === '*' && monthField === '*' && dowField === '*') {
    if (minField === '*' || minField === '*/1') {
      return {
        valid: true,
        mode: 'custom',
        customUnit: 'minute',
        interval: 1,
        minuteOfHour: 0,
        time: '09:00',
        weekdays: [1],
        dayOfMonth: 1,
        anchorDate: getTodayLocalDateString(),
        preserveInitialRecurrence: false,
        rawCron,
      }
    }
    const stepMatch = /^\*\/(\d+)$/.exec(minField)
    if (stepMatch) {
      const step = Number(stepMatch[1])
      if (MINUTE_INTERVAL_CHOICES.includes(step)) {
        return {
          valid: true,
          mode: 'custom',
          customUnit: 'minute',
          interval: step,
          minuteOfHour: 0,
          time: '09:00',
          weekdays: [1],
          dayOfMonth: 1,
          anchorDate: getTodayLocalDateString(),
          preserveInitialRecurrence: false,
          rawCron,
        }
      }
    }
  }

  // 2. Hourly interval: m * * * * or m */N * * *
  const singleMinute = parseSingleInt(minField, 0, 59)
  if (!normRec && singleMinute !== null && domField === '*' && monthField === '*' && dowField === '*') {
    if (hourField === '*' || hourField === '*/1') {
      return {
        valid: true,
        mode: 'custom',
        customUnit: 'hour',
        interval: 1,
        minuteOfHour: singleMinute,
        time: formatTimeHHmm(9, singleMinute),
        weekdays: [1],
        dayOfMonth: 1,
        anchorDate: getTodayLocalDateString(),
        preserveInitialRecurrence: false,
        rawCron,
      }
    }
    const stepMatch = /^\*\/(\d+)$/.exec(hourField)
    if (stepMatch) {
      const step = Number(stepMatch[1])
      if (HOUR_INTERVAL_CHOICES.includes(step)) {
        return {
          valid: true,
          mode: 'custom',
          customUnit: 'hour',
          interval: step,
          minuteOfHour: singleMinute,
          time: formatTimeHHmm(9, singleMinute),
          weekdays: [1],
          dayOfMonth: 1,
          anchorDate: getTodayLocalDateString(),
          preserveInitialRecurrence: false,
          rawCron,
        }
      }
    }
  }

  // 3. Calendar schedules require single minute, single hour, and month === '*'
  const singleHour = parseSingleInt(hourField, 0, 23)
  if (singleMinute !== null && singleHour !== null && monthField === '*') {
    const time = formatTimeHHmm(singleHour, singleMinute)

    // 3a. Daily / Custom Day: m h * * *
    if (domField === '*' && dowField === '*') {
      if (!normRec) {
        return {
          valid: true,
          mode: 'daily',
          customUnit: 'day',
          interval: 1,
          minuteOfHour: singleMinute,
          time,
          weekdays: [1],
          dayOfMonth: 1,
          anchorDate: getTodayLocalDateString(),
          preserveInitialRecurrence: false,
          rawCron,
        }
      }
      if (normRec.unit === 'day') {
        return {
          valid: true,
          mode: 'custom',
          customUnit: 'day',
          interval: normRec.interval,
          minuteOfHour: singleMinute,
          time,
          weekdays: [1],
          dayOfMonth: 1,
          anchorDate: normRec.anchor_date,
          preserveInitialRecurrence: normRec.interval === 1,
          rawCron,
        }
      }
    }

    // 3b. Weekdays / Weekly / Custom Week: m h * * dow
    if (domField === '*' && dowField !== '*') {
      const parsedDays = parseDowField(dowField)
      if (parsedDays) {
        const isMonFri = parsedDays.length === 5 && parsedDays.every((d, i) => d === i + 1)
        if (!normRec) {
          return {
            valid: true,
            mode: isMonFri ? 'weekdays' : 'weekly',
            customUnit: 'week',
            interval: 1,
            minuteOfHour: singleMinute,
            time,
            weekdays: parsedDays,
            dayOfMonth: 1,
            anchorDate: getTodayLocalDateString(),
            preserveInitialRecurrence: false,
            rawCron,
          }
        }
        if (normRec.unit === 'week') {
          return {
            valid: true,
            mode: 'custom',
            customUnit: 'week',
            interval: normRec.interval,
            minuteOfHour: singleMinute,
            time,
            weekdays: parsedDays,
            dayOfMonth: 1,
            anchorDate: normRec.anchor_date,
            preserveInitialRecurrence: normRec.interval === 1,
            rawCron,
          }
        }
      }
    }

    // 3c. Monthly / Custom Month: m h dom * *
    const singleDom = parseSingleInt(domField, 1, 31)
    if (singleDom !== null && dowField === '*') {
      if (!normRec || normRec.unit === 'month') {
        return {
          valid: true,
          mode: 'custom',
          customUnit: 'month',
          interval: normRec ? normRec.interval : 1,
          minuteOfHour: singleMinute,
          time,
          weekdays: [1],
          dayOfMonth: singleDom,
          anchorDate: normRec ? normRec.anchor_date : getTodayLocalDateString(),
          preserveInitialRecurrence: Boolean(normRec && normRec.interval === 1),
          rawCron,
        }
      }
    }
  }

  // 4. Valid 5-field cron that does not map losslessly (or mismatched recurrence unit) -> preserve as legacy
  return {
    valid: true,
    mode: 'legacy',
    customUnit: 'day',
    interval: 1,
    minuteOfHour: 0,
    time: '09:00',
    weekdays: [1],
    dayOfMonth: 1,
    anchorDate: getTodayLocalDateString(),
    preserveInitialRecurrence: false,
    legacyRecurrence: normRec,
    rawCron,
  }
}

export function buildScheduleFromState(state) {
  if (!state || typeof state !== 'object') {
    return { valid: false, error: 'error_schedule_invalid', cron: '', recurrence: null }
  }

  const mode = state.mode
  if (mode === 'legacy') {
    const recurrence = validateRecurrence(state.legacyRecurrence)
    const valid = isValidFiveFieldCron(state.rawCron) && recurrence.valid
    return {
      valid,
      error: valid ? '' : 'error_schedule_invalid',
      cron: state.rawCron || '',
      recurrence: recurrence.normalized || null,
    }
  }

  if (mode === 'daily') {
    if (!isValidTimeString(state.time)) {
      return { valid: false, error: 'error_time_required', cron: '', recurrence: null }
    }
    const [hh, mm] = state.time.trim().split(':').map(Number)
    return {
      valid: true,
      error: '',
      cron: `${mm} ${hh} * * *`,
      recurrence: null,
    }
  }

  if (mode === 'weekdays') {
    if (!isValidTimeString(state.time)) {
      return { valid: false, error: 'error_time_required', cron: '', recurrence: null }
    }
    const [hh, mm] = state.time.trim().split(':').map(Number)
    return {
      valid: true,
      error: '',
      cron: `${mm} ${hh} * * 1-5`,
      recurrence: null,
    }
  }

  if (mode === 'weekly') {
    const dow = serializeWeekdays(state.weekdays)
    if (!dow) {
      return { valid: false, error: 'error_weekdays_required', cron: '', recurrence: null }
    }
    if (!isValidTimeString(state.time)) {
      return { valid: false, error: 'error_time_required', cron: '', recurrence: null }
    }
    const [hh, mm] = state.time.trim().split(':').map(Number)
    return {
      valid: true,
      error: '',
      cron: `${mm} ${hh} * * ${dow}`,
      recurrence: null,
    }
  }

  if (mode === 'custom') {
    const unit = state.customUnit
    const interval = Number(state.interval)

    if (unit === 'minute') {
      if (!Number.isInteger(interval) || !MINUTE_INTERVAL_CHOICES.includes(interval)) {
        return { valid: false, error: 'error_interval_invalid', min: 1, max: 30, cron: '', recurrence: null }
      }
      return {
        valid: true,
        error: '',
        cron: interval === 1 ? '* * * * *' : `*/${interval} * * * *`,
        recurrence: null,
      }
    }

    if (unit === 'hour') {
      if (!Number.isInteger(interval) || !HOUR_INTERVAL_CHOICES.includes(interval)) {
        return { valid: false, error: 'error_interval_invalid', min: 1, max: 12, cron: '', recurrence: null }
      }
      const minOfHour = Number(state.minuteOfHour)
      if (!Number.isInteger(minOfHour) || minOfHour < 0 || minOfHour > 59) {
        return { valid: false, error: 'error_time_required', cron: '', recurrence: null }
      }
      return {
        valid: true,
        error: '',
        cron: interval === 1 ? `${minOfHour} * * * *` : `${minOfHour} */${interval} * * *`,
        recurrence: null,
      }
    }

    const limits = CALENDAR_INTERVAL_LIMITS[unit]
    if (!limits) {
      return { valid: false, error: 'error_schedule_invalid', cron: '', recurrence: null }
    }
    if (!Number.isInteger(interval) || interval < limits.min || interval > limits.max) {
      return {
        valid: false,
        error: 'error_interval_invalid',
        min: limits.min,
        max: limits.max,
        cron: '',
        recurrence: null,
      }
    }

    let dow = '*'
    let dom = '*'
    if (unit === 'week') {
      dow = serializeWeekdays(state.weekdays)
      if (!dow) {
        return { valid: false, error: 'error_weekdays_required', cron: '', recurrence: null }
      }
    } else if (unit === 'month') {
      const d = Number(state.dayOfMonth)
      if (!Number.isInteger(d) || d < 1 || d > 31) {
        return { valid: false, error: 'error_day_of_month_invalid', cron: '', recurrence: null }
      }
      dom = String(d)
    }

    if (!isValidTimeString(state.time)) {
      return { valid: false, error: 'error_time_required', cron: '', recurrence: null }
    }
    const [hh, mm] = state.time.trim().split(':').map(Number)

    const needsRecurrence = interval > 1 || Boolean(state.preserveInitialRecurrence)
    let recurrence = null
    if (needsRecurrence) {
      if (!isValidAnchorDate(state.anchorDate)) {
        return { valid: false, error: 'error_anchor_date_required', cron: '', recurrence: null }
      }
      recurrence = {
        unit,
        interval,
        anchor_date: state.anchorDate.trim(),
      }
    }

    return {
      valid: true,
      error: '',
      cron: `${mm} ${hh} ${dom} * ${dow}`,
      recurrence,
    }
  }

  return { valid: false, error: 'error_schedule_invalid', cron: '', recurrence: null }
}

export function translateScheduleKey(t, shortKey, params = {}) {
  return t(`components.schedule_editor.${shortKey}`, params)
}

export function formatWeekdayList(weekdays, t, short = false) {
  const ordered = WEEKDAY_ORDER.filter(d => (weekdays || []).includes(d))
  const labels = ordered.map(d => translateScheduleKey(t, `${short ? 'weekday_short_' : 'weekday_'}${d}`))
  if (labels.length === 0) return ''
  if (labels.length === 1) return labels[0]
  const comma = translateScheduleKey(t, 'list_comma')
  const andSep = translateScheduleKey(t, 'list_and')
  return `${labels.slice(0, -1).join(comma)}${andSep}${labels[labels.length - 1]}`
}

export function formatTimezoneHint(timezone, t) {
  const tz = timezone || getLocalTimezone()
  if (tz === 'Asia/Shanghai' || tz === 'Asia/Chongqing' || tz === 'PRC') {
    return translateScheduleKey(t, 'Zone_Asia_Shanghai')
  }
  if (tz === 'UTC' || tz === 'Etc/UTC') {
    return translateScheduleKey(t, 'Zone_UTC')
  }
  const slashIdx = tz.lastIndexOf('/')
  return slashIdx >= 0 ? tz.slice(slashIdx + 1).replaceAll('_', ' ') : tz
}

export function formatSchedule(cronExpression, recurrence = null, t = null) {
  const raw = typeof cronExpression === 'string' ? cronExpression.trim() : ''
  if (!raw) return translateScheduleKey(t, 'summary_unconfigured')

  const parsed = parseSchedule(raw, recurrence)
  if (!parsed.valid) {
    return translateScheduleKey(t, 'summary_custom_cron', { cron: raw })
  }

  if (parsed.mode === 'legacy') {
    return translateScheduleKey(t, 'summary_custom_cron', { cron: raw })
  }

  if (parsed.mode === 'daily') {
    return translateScheduleKey(t, 'summary_daily', { time: parsed.time })
  }

  if (parsed.mode === 'weekdays') {
    return translateScheduleKey(t, 'summary_weekdays', { time: parsed.time })
  }

  if (parsed.mode === 'weekly') {
    const days = formatWeekdayList(parsed.weekdays, t, false)
    return translateScheduleKey(t, 'summary_weekly', { days, time: parsed.time })
  }

  if (parsed.mode === 'custom') {
    const unit = parsed.customUnit
    const interval = parsed.interval
    if (unit === 'minute') {
      return interval === 1
        ? translateScheduleKey(t, 'summary_every_minute')
        : translateScheduleKey(t, 'summary_every_n_minutes', { interval })
    }
    if (unit === 'hour') {
      const minute = String(parsed.minuteOfHour).padStart(2, '0')
      return interval === 1
        ? translateScheduleKey(t, 'summary_every_hour', { minute })
        : translateScheduleKey(t, 'summary_every_n_hours', { interval, minute })
    }
    const fromSuffix =
      interval > 1 && parsed.anchorDate
        ? translateScheduleKey(t, 'summary_from_date', { date: parsed.anchorDate })
        : ''
    if (unit === 'day') {
      const base =
        interval === 1
          ? translateScheduleKey(t, 'summary_daily', { time: parsed.time })
          : translateScheduleKey(t, 'summary_every_n_days', { interval, time: parsed.time })
      return `${base}${fromSuffix}`
    }
    if (unit === 'week') {
      const days = formatWeekdayList(parsed.weekdays, t, false)
      const base =
        interval === 1
          ? translateScheduleKey(t, 'summary_weekly', { days, time: parsed.time })
          : translateScheduleKey(t, 'summary_every_n_weeks', { interval, days, time: parsed.time })
      return `${base}${fromSuffix}`
    }
    if (unit === 'month') {
      const base =
        interval === 1
          ? translateScheduleKey(t, 'summary_monthly', { day: parsed.dayOfMonth, time: parsed.time })
          : translateScheduleKey(t, 'summary_every_n_months', { interval, day: parsed.dayOfMonth, time: parsed.time })
      return `${base}${fromSuffix}`
    }
  }

  return translateScheduleKey(t, 'summary_custom_cron', { cron: raw })
}
