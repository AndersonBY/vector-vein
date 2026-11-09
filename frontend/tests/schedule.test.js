import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import {
  MINUTE_INTERVAL_CHOICES,
  HOUR_INTERVAL_CHOICES,
  parseSchedule,
  buildScheduleFromState,
  formatSchedule,
  validateRecurrence,
  isValidFiveFieldCron,
  parseDowField,
  formatTimezoneHint,
} from '../src/utils/schedule.js'

const makeT = localeDict => (key, params = {}) => {
  const short = key.replace(/^components\.schedule_editor\./, '')
  let str = localeDict[short]
  if (!str) return key
  for (const [k, v] of Object.entries(params)) {
    str = str.replaceAll(`{${k}}`, String(v))
  }
  return str
}

test('Cron weekday ranges and large steps retain backend semantics', () => {
  assert.deepEqual(parseDowField('7-7'), [0])
  assert.deepEqual(parseDowField('1-7'), [1, 2, 3, 4, 5, 6, 0])
  for (const range of ['7-6', 'MON-SUN']) {
    assert.equal(parseDowField(range), null)
    assert.equal(isValidFiveFieldCron(`0 9 * * ${range}`), false)
  }
  assert.deepEqual(parseSchedule('0 9 * * 7-7').weekdays, [0])
  for (const cron of ['*/90 * * * *', '0 */30 * * *']) {
    assert.equal(parseSchedule(cron).valid, true)
    assert.equal(parseSchedule(cron).mode, 'legacy')
  }
  assert.equal(isValidFiveFieldCron('*/0 * * * *'), false)
  assert.equal(formatTimezoneHint('Asia/Urumqi', makeT({})), 'Urumqi')
  assert.equal(validateRecurrence({ unit: 'day', interval: 2, anchor_date: '2026-11-06', extra: true }).valid, false)
  const legacyRule = { unit: 'day', interval: 2, anchor_date: '2026-11-06' }
  const legacy = parseSchedule('0 9,18 * * *', legacyRule)
  assert.equal(legacy.mode, 'legacy')
  assert.deepEqual(buildScheduleFromState(legacy).recurrence, legacyRule)
})

test('parseSchedule and buildScheduleFromState roundtrip standard presets, aliases, Sunday=7, and custom intervals', () => {
  // 1. Daily
  const daily = parseSchedule('30 9 * * *', null)
  assert.equal(daily.valid, true)
  assert.equal(daily.mode, 'daily')
  assert.equal(daily.time, '09:30')
  assert.deepEqual(buildScheduleFromState(daily), {
    valid: true,
    error: '',
    cron: '30 9 * * *',
    recurrence: null,
  })

  // 2. Weekdays (1-5 and MON-FRI)
  const weekdays1 = parseSchedule('0 9 * * 1-5', null)
  assert.equal(weekdays1.valid, true)
  assert.equal(weekdays1.mode, 'weekdays')
  assert.deepEqual(weekdays1.weekdays, [1, 2, 3, 4, 5])
  const weekdaysAlias = parseSchedule('15 8 * * MON-FRI', null)
  assert.equal(weekdaysAlias.valid, true)
  assert.equal(weekdaysAlias.mode, 'weekdays')
  assert.equal(weekdaysAlias.time, '08:15')

  // 3. Weekly with Sunday=7 and aliases
  const weeklySun7 = parseSchedule('0 18 * * 1,3,7', null)
  assert.equal(weeklySun7.valid, true)
  assert.equal(weeklySun7.mode, 'weekly')
  assert.deepEqual(weeklySun7.weekdays, [1, 3, 0])
  assert.deepEqual(buildScheduleFromState(weeklySun7), {
    valid: true,
    error: '',
    cron: '0 18 * * 1,3,0',
    recurrence: null,
  })

  const fullWeekRange = parseSchedule('0 9 * * 1-7', null)
  assert.equal(fullWeekRange.valid, true)
  assert.equal(fullWeekRange.mode, 'weekly')
  assert.deepEqual(fullWeekRange.weekdays, [1, 2, 3, 4, 5, 6, 0])

  // 4. Every N minutes & Every N hours
  for (const m of MINUTE_INTERVAL_CHOICES) {
    const cron = m === 1 ? '* * * * *' : `*/${m} * * * *`
    const parsed = parseSchedule(cron, null)
    assert.equal(parsed.valid, true)
    assert.equal(parsed.mode, 'custom')
    assert.equal(parsed.customUnit, 'minute')
    assert.equal(parsed.interval, m)
    assert.equal(buildScheduleFromState(parsed).cron, cron)
  }
  for (const h of HOUR_INTERVAL_CHOICES) {
    const cron = h === 1 ? '15 * * * *' : `15 */${h} * * *`
    const parsed = parseSchedule(cron, null)
    assert.equal(parsed.valid, true)
    assert.equal(parsed.mode, 'custom')
    assert.equal(parsed.customUnit, 'hour')
    assert.equal(parsed.interval, h)
    assert.equal(parsed.minuteOfHour, 15)
    assert.equal(buildScheduleFromState(parsed).cron, cron)
  }

  // 5. Custom calendar intervals (day, week, month) with recurrence
  const every3Days = parseSchedule('0 10 * * *', { unit: 'day', interval: 3, anchor_date: '2026-11-06' })
  assert.equal(every3Days.valid, true)
  assert.equal(every3Days.mode, 'custom')
  assert.equal(every3Days.customUnit, 'day')
  assert.equal(every3Days.interval, 3)
  assert.equal(every3Days.anchorDate, '2026-11-06')
  assert.deepEqual(buildScheduleFromState(every3Days), {
    valid: true,
    error: '',
    cron: '0 10 * * *',
    recurrence: { unit: 'day', interval: 3, anchor_date: '2026-11-06' },
  })

  const every2Weeks = parseSchedule('45 14 * * 2,4', { unit: 'week', interval: 2, anchor_date: '2026-11-06' })
  assert.equal(every2Weeks.valid, true)
  assert.equal(every2Weeks.mode, 'custom')
  assert.equal(every2Weeks.customUnit, 'week')
  assert.deepEqual(every2Weeks.weekdays, [2, 4])
  assert.deepEqual(buildScheduleFromState(every2Weeks), {
    valid: true,
    error: '',
    cron: '45 14 * * 2,4',
    recurrence: { unit: 'week', interval: 2, anchor_date: '2026-11-06' },
  })

  const every6Months = parseSchedule('0 9 31 * *', { unit: 'month', interval: 6, anchor_date: '2026-01-31' })
  assert.equal(every6Months.valid, true)
  assert.equal(every6Months.mode, 'custom')
  assert.equal(every6Months.customUnit, 'month')
  assert.equal(every6Months.dayOfMonth, 31)
  assert.deepEqual(buildScheduleFromState(every6Months), {
    valid: true,
    error: '',
    cron: '0 9 31 * *',
    recurrence: { unit: 'month', interval: 6, anchor_date: '2026-01-31' },
  })
})

test('parseSchedule preserves complex valid Cron expressions as legacy without silent coercion and rejects invalid Cron/recurrence', () => {
  const complexCrons = [
    '0 9,18 * * *',      // multiple hours
    '0 9-17 * * 1-5',    // hour range
    '*/7 * * * *',       // non-divisor minute step
    '0 */5 * * *',       // non-divisor hour step
    '0 9 1,15 * *',      // multiple days of month
    '0 9 * 1,6 *',       // specific months
    '0 9 15 * 1',        // both DOM and DOW specified (OR semantics)
  ]
  for (const expr of complexCrons) {
    const parsed = parseSchedule(expr, null)
    assert.equal(parsed.valid, true, `Expected ${expr} to be valid legacy cron`)
    assert.equal(parsed.mode, 'legacy', `Expected ${expr} to stay in legacy mode`)
    assert.equal(parsed.rawCron, expr)
    const built = buildScheduleFromState(parsed)
    assert.equal(built.valid, true)
    assert.equal(built.cron, expr)
    assert.equal(built.recurrence, null)
  }

  // Invalid cron syntax
  for (const bad of ['', 'invalid', '0 25 * * *', '60 9 * * *', '0 9 32 * *', '0 9 * 13 *', '0 9 * * 8']) {
    assert.equal(parseSchedule(bad, null).valid, false, `Expected ${bad} to be invalid`)
  }

  // Invalid recurrence bounds
  assert.equal(validateRecurrence({ unit: 'day', interval: 0, anchor_date: '2026-11-06' }).valid, false)
  assert.equal(validateRecurrence({ unit: 'day', interval: 366, anchor_date: '2026-11-06' }).valid, false)
  assert.equal(validateRecurrence({ unit: 'week', interval: 53, anchor_date: '2026-11-06' }).valid, false)
  assert.equal(validateRecurrence({ unit: 'month', interval: 13, anchor_date: '2026-11-06' }).valid, false)
  assert.equal(validateRecurrence({ unit: 'day', interval: 2, anchor_date: '2026-02-30' }).valid, false)
})

test('formatSchedule renders localized summaries for zh-CN and en-US across presets, custom intervals, and legacy Cron', async () => {
  const locales = Object.fromEntries(await Promise.all(['zh-CN', 'en-US'].map(async locale => [locale, JSON.parse(await readFile(new URL(`../src/locales/${locale}.json`, import.meta.url), 'utf8')).components.schedule_editor])))
  const tZh = makeT(locales['zh-CN'])
  const tEn = makeT(locales['en-US'])

  assert.equal(formatSchedule('0 9 * * *', null, tZh), '每天 09:00')
  assert.equal(formatSchedule('0 9 * * *', null, tEn), 'Daily at 09:00')

  assert.equal(formatSchedule('30 8 * * 1-5', null, tZh), '每个工作日 08:30')
  assert.equal(formatSchedule('30 8 * * 1-5', null, tEn), 'Weekdays at 08:30')

  assert.equal(formatSchedule('0 9 * * 1,3,5', null, tZh), '每周 星期一、星期三和星期五 09:00')
  assert.equal(formatSchedule('0 9 * * 1,3,5', null, tEn), 'Weekly on Monday, Wednesday and Friday at 09:00')

  assert.equal(
    formatSchedule('0 9 * * 1,5', { unit: 'week', interval: 2, anchor_date: '2026-11-06' }, tZh),
    '每 2 周（星期一和星期五）09:00（自 2026-11-06 起）',
  )
  assert.equal(
    formatSchedule('0 9 15 * *', { unit: 'month', interval: 3, anchor_date: '2026-11-15' }, tEn),
    'Every 3 months on day 15 at 09:00 (starting 2026-11-15)',
  )
  assert.equal(formatSchedule('0 9,18 * * *', null, tZh), '已保存的自定义计划')
})
