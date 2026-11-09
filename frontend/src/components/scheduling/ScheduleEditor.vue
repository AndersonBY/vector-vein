<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Down } from '@/icons'
import {
  MINUTE_INTERVAL_CHOICES,
  HOUR_INTERVAL_CHOICES,
  WEEKDAY_ORDER,
  CALENDAR_INTERVAL_LIMITS,
  DEFAULT_TIMEZONES,
  getLocalTimezone,
  getTodayLocalDateString,
  parseSchedule,
  buildScheduleFromState,
  translateScheduleKey,
  formatWeekdayList,
  formatTimezoneHint,
} from '@/utils/schedule'

const props = defineProps({
  modelValue: {
    type: String,
    default: '0 9 * * *',
  },
  recurrence: {
    type: Object,
    default: null,
  },
  timezone: {
    type: String,
    default: () => getLocalTimezone(),
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:modelValue',
  'update:recurrence',
  'update:timezone',
  'validity-change',
])

const { t } = useI18n()
const tr = (key, params = {}) => translateScheduleKey(t, key, params)

const draft = reactive({
  mode: 'daily',
  customUnit: 'week',
  interval: 1,
  minuteOfHour: 0,
  time: '09:00',
  weekdays: [1],
  dayOfMonth: 1,
  anchorDate: getTodayLocalDateString(),
  preserveInitialRecurrence: false,
  rawCron: '0 9 * * *',
  legacyRecurrence: null,
})

const advancedOpen = ref(false)
const weekdaysOpen = ref(false)
const lastEmittedCron = ref(null)
const lastEmittedRecJson = ref(null)
const lastReportedValidity = ref(null)
const sourceError = ref('')

function recJsonOf(recurrence) {
  return JSON.stringify(recurrence ?? null)
}

function emitValidityIfChanged(valid) {
  const boolVal = Boolean(valid)
  if (lastReportedValidity.value !== boolVal) {
    lastReportedValidity.value = boolVal
    emit('validity-change', boolVal)
  }
}

function hydrateFromProps(cronValue, recurrenceValue) {
  const parsed = parseSchedule(cronValue, recurrenceValue)
  sourceError.value = parsed.valid ? '' : parsed.error
  if (parsed.valid) {
    draft.mode = parsed.mode
    draft.customUnit = parsed.customUnit
    draft.interval = parsed.interval
    draft.minuteOfHour = parsed.minuteOfHour
    draft.time = parsed.time
    draft.weekdays = [...parsed.weekdays]
    draft.dayOfMonth = parsed.dayOfMonth
    draft.anchorDate = parsed.anchorDate
    draft.preserveInitialRecurrence = parsed.preserveInitialRecurrence
    draft.rawCron = parsed.rawCron
    draft.legacyRecurrence = parsed.legacyRecurrence || null
  } else {
    draft.mode = 'legacy'
    draft.rawCron = typeof cronValue === 'string' ? cronValue.trim() : ''
    draft.preserveInitialRecurrence = false
  }
}

hydrateFromProps(props.modelValue, props.recurrence)

onMounted(() => {
  emitValidityIfChanged(buildResult.value.valid)
})

watch(
  () => [props.modelValue, recJsonOf(props.recurrence)],
  ([nextCron, nextRecJson], [prevCron, prevRecJson]) => {
    const normCron = typeof nextCron === 'string' ? nextCron.trim() : ''
    const cronChanged = nextCron !== prevCron
    const recChanged = nextRecJson !== prevRecJson

    const cronMatchesOwnEmit = lastEmittedCron.value !== null && normCron === lastEmittedCron.value
    const recMatchesOwnEmit = lastEmittedRecJson.value !== null && nextRecJson === lastEmittedRecJson.value

    if (
      (cronChanged && !recChanged && cronMatchesOwnEmit) ||
      (!cronChanged && recChanged && recMatchesOwnEmit) ||
      (cronMatchesOwnEmit && recMatchesOwnEmit)
    ) {
      if (cronMatchesOwnEmit && recMatchesOwnEmit) {
        lastEmittedCron.value = null
        lastEmittedRecJson.value = null
      }
      return
    }

    lastEmittedCron.value = null
    lastEmittedRecJson.value = null
    hydrateFromProps(props.modelValue, props.recurrence)
  },
)

const buildResult = computed(() => {
  const built = buildScheduleFromState(draft)
  if (sourceError.value) return { ...built, valid: false, error: sourceError.value }
  try {
    new Intl.DateTimeFormat('en', { timeZone: props.timezone || getLocalTimezone() })
  } catch {
    return { ...built, valid: false, error: 'error_timezone_invalid' }
  }
  return built
})

watch(() => buildResult.value.valid, emitValidityIfChanged)

const validationMessage = computed(() => {
  const res = buildResult.value
  if (res.valid || !res.error) return ''
  return tr(res.error, { min: res.min, max: res.max })
})

function commitUserEdit() {
  if (props.disabled) return
  sourceError.value = ''
  const res = buildScheduleFromState(draft)
  emitValidityIfChanged(buildResult.value.valid)
  if (!res.valid) return

  lastEmittedCron.value = res.cron
  lastEmittedRecJson.value = recJsonOf(res.recurrence)
  if (res.cron !== props.modelValue) {
    emit('update:modelValue', res.cron)
  }
  const currentRecJson = recJsonOf(props.recurrence)
  const nextRecJson = recJsonOf(res.recurrence)
  if (currentRecJson !== nextRecJson) {
    emit('update:recurrence', res.recurrence)
  }
}

function handleModeChange(nextMode) {
  if (props.disabled) return
  draft.mode = nextMode
  draft.preserveInitialRecurrence = false
  if (!draft.time) draft.time = '09:00'

  if (nextMode === 'daily') {
    draft.customUnit = 'day'
    draft.interval = 1
  } else if (nextMode === 'weekdays') {
    draft.customUnit = 'week'
    draft.interval = 1
    draft.weekdays = [1, 2, 3, 4, 5]
  } else if (nextMode === 'weekly') {
    draft.customUnit = 'week'
    draft.interval = 1
    if (!Array.isArray(draft.weekdays) || draft.weekdays.length === 0) {
      draft.weekdays = [1]
    }
  } else if (nextMode === 'custom') {
    if (!['minute', 'hour', 'day', 'week', 'month'].includes(draft.customUnit)) {
      draft.customUnit = 'week'
    }
    if (draft.customUnit === 'week' && (!Array.isArray(draft.weekdays) || draft.weekdays.length === 0)) {
      draft.weekdays = [1, 2, 3, 4, 5, 6, 0]
    }
    if (!draft.anchorDate) {
      draft.anchorDate = getTodayLocalDateString()
    }
  }
  commitUserEdit()
}

function handleCustomUnitChange(nextUnit) {
  if (props.disabled) return
  draft.customUnit = nextUnit
  draft.preserveInitialRecurrence = false
  if (nextUnit === 'minute') {
    if (!MINUTE_INTERVAL_CHOICES.includes(Number(draft.interval))) {
      draft.interval = 5
    }
  } else if (nextUnit === 'hour') {
    if (!HOUR_INTERVAL_CHOICES.includes(Number(draft.interval))) {
      draft.interval = 1
    }
  } else {
    const limits = CALENDAR_INTERVAL_LIMITS[nextUnit]
    const n = Number(draft.interval)
    if (!Number.isInteger(n) || n < limits.min || n > limits.max) {
      draft.interval = 1
    }
    if (nextUnit === 'week' && (!Array.isArray(draft.weekdays) || draft.weekdays.length === 0)) {
      draft.weekdays = [1]
    }
    if (nextUnit === 'month' && (!Number.isInteger(draft.dayOfMonth) || draft.dayOfMonth < 1 || draft.dayOfMonth > 31)) {
      draft.dayOfMonth = 1
    }
    if (!draft.anchorDate) {
      draft.anchorDate = getTodayLocalDateString()
    }
  }
  commitUserEdit()
}

function handleIntervalSelect(val) {
  if (props.disabled) return
  draft.interval = Number(val)
  draft.preserveInitialRecurrence = false
  commitUserEdit()
}

function handleCalendarIntervalInput(event) {
  if (props.disabled) return
  const raw = event?.target ? event.target.value : event
  const parsed = raw === '' || raw === null ? Number.NaN : Number(raw)
  draft.interval = parsed
  if (Number.isInteger(parsed) && parsed > 1 && !draft.anchorDate) {
    draft.anchorDate = getTodayLocalDateString()
  }
  commitUserEdit()
}

function handleMinuteOfHourChange(val) {
  if (props.disabled) return
  draft.minuteOfHour = Number(val)
  commitUserEdit()
}

function handleWeekdaysChange(nextDays) {
  if (props.disabled) return
  const arr = Array.isArray(nextDays) ? nextDays.map(Number) : []
  draft.weekdays = WEEKDAY_ORDER.filter(d => arr.includes(d))
  commitUserEdit()
}

function handleDayOfMonthChange(val) {
  if (props.disabled) return
  draft.dayOfMonth = Number(val)
  commitUserEdit()
}

function handleAnchorDateInput(event) {
  if (props.disabled) return
  const val = event?.target ? event.target.value : String(event || '')
  draft.anchorDate = val
  commitUserEdit()
}

function handleTimeChange(val) {
  if (props.disabled) return
  draft.time = typeof val === 'string' ? val : ''
  commitUserEdit()
}

function handleTimezoneChange(nextTz) {
  if (props.disabled || !nextTz) return
  if (nextTz !== props.timezone) {
    emit('update:timezone', nextTz)
  }
}

const effectiveTimezone = computed(() => props.timezone || getLocalTimezone())
const timezoneHint = computed(() => formatTimezoneHint(effectiveTimezone.value, t))

const timezoneOptions = computed(() => {
  const set = new Set([getLocalTimezone(), effectiveTimezone.value, ...DEFAULT_TIMEZONES].filter(Boolean))
  return [...set].map(tz => ({
    value: tz,
    label: `${tz} (${formatTimezoneHint(tz, t)})`,
  }))
})

const modeOptions = computed(() => {
  const opts = [
    { value: 'daily', label: tr('frequency_daily') },
    { value: 'weekdays', label: tr('frequency_weekdays') },
    { value: 'weekly', label: tr('frequency_weekly') },
    { value: 'custom', label: tr('frequency_custom') },
  ]
  if (draft.mode === 'legacy') {
    opts.push({ value: 'legacy', label: tr('frequency_legacy'), disabled: true })
  }
  return opts
})

const customUnitOptions = computed(() => [
  { value: 'minute', label: tr('unit_minute') },
  { value: 'hour', label: tr('unit_hour') },
  { value: 'day', label: tr('unit_day') },
  { value: 'week', label: tr('unit_week') },
  { value: 'month', label: tr('unit_month') },
])

const minuteIntervalOptions = computed(() =>
  MINUTE_INTERVAL_CHOICES.map(n => ({ value: n, label: `${n}` })),
)

const hourIntervalOptions = computed(() =>
  HOUR_INTERVAL_CHOICES.map(n => ({ value: n, label: `${n}` })),
)

const minuteOfHourOptions = computed(() =>
  Array.from({ length: 60 }, (_, m) => ({
    value: m,
    label: tr('minute_of_hour_value', { minute: String(m).padStart(2, '0') }),
  })),
)

const dayOfMonthOptions = computed(() =>
  Array.from({ length: 31 }, (_, i) => ({
    value: i + 1,
    label: tr('day_of_month_value', { day: i + 1 }),
  })),
)

const weekdayOptions = computed(() =>
  WEEKDAY_ORDER.map(d => ({
    value: d,
    label: tr(`weekday_${d}`),
  })),
)

const weekdaySummaryText = computed(() => {
  const summary = formatWeekdayList(draft.weekdays, t, false)
  return summary || tr('error_weekdays_required')
})

const showWeekdaysRow = computed(
  () => draft.mode === 'weekly' || (draft.mode === 'custom' && draft.customUnit === 'week'),
)

const showDayOfMonthRow = computed(
  () => draft.mode === 'custom' && draft.customUnit === 'month',
)

const showAnchorDateRow = computed(
  () =>
    draft.mode === 'custom' &&
    ['day', 'week', 'month'].includes(draft.customUnit) &&
    (Number(draft.interval) > 1 || draft.preserveInitialRecurrence),
)

const showTimeRow = computed(
  () =>
    draft.mode === 'daily' ||
    draft.mode === 'weekdays' ||
    draft.mode === 'weekly' ||
    (draft.mode === 'custom' && ['day', 'week', 'month'].includes(draft.customUnit)),
)

const calendarLimits = computed(
  () => CALENDAR_INTERVAL_LIMITS[draft.customUnit] || { min: 1, max: 365 },
)

defineExpose({
  draft,
  advancedOpen,
  buildResult,
  validationMessage,
  weekdaySummaryText,
  handleModeChange,
  handleCustomUnitChange,
  handleIntervalSelect,
  handleCalendarIntervalInput,
  handleMinuteOfHourChange,
  handleWeekdaysChange,
  handleDayOfMonthChange,
  handleAnchorDateInput,
  handleTimeChange,
  handleTimezoneChange,
})
</script>

<template>
  <div class="schedule-editor nodrag nowheel" :class="{ 'is-disabled': disabled }">
    <div class="schedule-group" role="group" :aria-label="tr('repeat')">
      <!-- Row 1: Primary Repeat Mode -->
      <div class="schedule-row">
        <span class="schedule-row-label">{{ tr('repeat') }}</span>
        <div class="schedule-row-control">
          <a-select
            :value="draft.mode"
            class="schedule-borderless-select"
            :bordered="false"
            :disabled="disabled"
            :dropdown-match-select-width="false"
            :aria-label="tr('repeat')"
            @change="handleModeChange"
          >
            <a-select-opt-group :label="tr('frequency_group')">
              <a-select-option
                v-for="opt in modeOptions"
                :key="opt.value"
                :value="opt.value"
                :disabled="opt.disabled"
              >
                {{ opt.label }}
              </a-select-option>
            </a-select-opt-group>
          </a-select>
        </div>
      </div>

      <!-- Custom Row: Repeat Unit -->
      <div v-if="draft.mode === 'custom'" class="schedule-row">
        <span class="schedule-row-label">{{ tr('repeat') }}</span>
        <div class="schedule-row-control">
          <a-select
            :value="draft.customUnit"
            class="schedule-borderless-select"
            :bordered="false"
            :disabled="disabled"
            :dropdown-match-select-width="false"
            :options="customUnitOptions"
            :aria-label="tr('unit_label')"
            @change="handleCustomUnitChange"
          />
        </div>
      </div>

      <!-- Custom Row: Interval -->
      <div v-if="draft.mode === 'custom'" class="schedule-row">
        <span class="schedule-row-label">{{ tr('every') }}</span>
        <div class="schedule-row-control schedule-interval-control">
          <a-select
            v-if="draft.customUnit === 'minute'"
            :value="draft.interval"
            class="schedule-borderless-select schedule-interval-select"
            :bordered="false"
            :disabled="disabled"
            :dropdown-match-select-width="false"
            :options="minuteIntervalOptions"
            :aria-label="tr('every')"
            @change="handleIntervalSelect"
          />
          <a-select
            v-else-if="draft.customUnit === 'hour'"
            :value="draft.interval"
            class="schedule-borderless-select schedule-interval-select"
            :bordered="false"
            :disabled="disabled"
            :dropdown-match-select-width="false"
            :options="hourIntervalOptions"
            :aria-label="tr('every')"
            @change="handleIntervalSelect"
          />
          <input
            v-else
            type="number"
            class="schedule-inline-input schedule-interval-number"
            :value="Number.isFinite(draft.interval) ? draft.interval : ''"
            :min="calendarLimits.min"
            :max="calendarLimits.max"
            step="1"
            :disabled="disabled"
            :aria-label="tr('every')"
            @input="handleCalendarIntervalInput"
          />
          <span class="schedule-unit-suffix">{{ tr(`interval_unit_${draft.customUnit}`) }}</span>
        </div>
      </div>

      <!-- Custom Hourly Row: Minute of Hour -->
      <div v-if="draft.mode === 'custom' && draft.customUnit === 'hour'" class="schedule-row">
        <span class="schedule-row-label">{{ tr('minute_of_hour') }}</span>
        <div class="schedule-row-control">
          <a-select
            :value="draft.minuteOfHour"
            class="schedule-borderless-select"
            :bordered="false"
            :disabled="disabled"
            :dropdown-match-select-width="false"
            :options="minuteOfHourOptions"
            :aria-label="tr('minute_of_hour')"
            @change="handleMinuteOfHourChange"
          />
        </div>
      </div>

      <!-- Weekly / Custom Week Row: Weekdays Selection -->
      <div v-if="showWeekdaysRow" class="schedule-row schedule-row-weekdays">
        <span class="schedule-row-label">{{ tr('on_days') }}</span>
        <div class="schedule-row-control schedule-weekdays-control">
          <a-dropdown v-model:open="weekdaysOpen" :trigger="['click']" :disabled="disabled" placement="bottomRight">
            <button
              type="button"
              class="schedule-weekdays-trigger"
              :class="{ 'is-invalid': draft.weekdays.length === 0 }"
              :disabled="disabled"
              :aria-label="tr('on_days')"
            >
              <span class="schedule-weekdays-summary">{{ weekdaySummaryText }}</span>
              <Down :size="12" aria-hidden="true" />
            </button>
            <template #overlay>
              <div class="schedule-weekdays-dropdown" @click.stop>
                <a-checkbox-group
                  :value="draft.weekdays"
                  :disabled="disabled"
                  class="schedule-weekdays-checkboxes"
                  @change="handleWeekdaysChange"
                >
                  <a-checkbox v-for="day in weekdayOptions" :key="day.value" :value="day.value">
                    {{ day.label }}
                  </a-checkbox>
                </a-checkbox-group>
              </div>
            </template>
          </a-dropdown>
        </div>
      </div>

      <!-- Custom Month Row: Day of Month -->
      <div v-if="showDayOfMonthRow" class="schedule-row">
        <span class="schedule-row-label">{{ tr('day_of_month') }}</span>
        <div class="schedule-row-control">
          <a-select
            :value="draft.dayOfMonth"
            class="schedule-borderless-select"
            :bordered="false"
            :disabled="disabled"
            :dropdown-match-select-width="false"
            :options="dayOfMonthOptions"
            :aria-label="tr('day_of_month')"
            @change="handleDayOfMonthChange"
          />
        </div>
      </div>

      <!-- Custom Calendar Interval > 1 Row: Start / Anchor Date -->
      <div v-if="showAnchorDateRow" class="schedule-row">
        <span class="schedule-row-label">{{ tr('start_date') }}</span>
        <div class="schedule-row-control">
          <input
            type="date"
            class="schedule-inline-input schedule-date-input"
            :value="draft.anchorDate"
            :disabled="disabled"
            :aria-label="tr('start_date')"
            @input="handleAnchorDateInput"
          />
        </div>
      </div>

      <!-- Time of Day Row -->
      <div v-if="showTimeRow" class="schedule-row">
        <span class="schedule-row-label">
          {{ draft.mode === 'custom' ? tr('start_time') : tr('time') }}
        </span>
        <div class="schedule-row-control schedule-time-control">
          <span class="schedule-tz-hint">{{ timezoneHint }}</span>
          <a-time-picker
            :value="draft.time || undefined"
            format="HH:mm"
            value-format="HH:mm"
            :bordered="false"
            :allow-clear="false"
            :disabled="disabled"
            class="schedule-time-picker"
            :aria-label="draft.mode === 'custom' ? tr('start_time') : tr('time')"
            @change="handleTimeChange"
          />
        </div>
      </div>

      <!-- Saved Legacy / Non-lossless Cron Row -->
      <div v-if="draft.mode === 'legacy'" class="schedule-row schedule-legacy-row">
        <div class="schedule-legacy-body">
          <div class="schedule-legacy-title">
            {{ tr('legacy_preserve_title', { cron: draft.rawCron || '—' }) }}
          </div>
          <div class="schedule-legacy-hint">{{ tr('legacy_preserve_hint') }}</div>
        </div>
      </div>
    </div>

    <div v-if="validationMessage" class="schedule-validation-error" role="alert">
      {{ validationMessage }}
    </div>

    <!-- Collapsible Advanced Section (Timezone) -->
    <div class="schedule-advanced">
      <button
        type="button"
        class="schedule-advanced-toggle"
        :aria-expanded="advancedOpen"
        @click="advancedOpen = !advancedOpen"
      >
        <span>{{ tr('advanced') }}</span>
        <Down :size="12" class="schedule-advanced-chevron" :class="{ 'is-open': advancedOpen }" aria-hidden="true" />
      </button>

      <div v-if="advancedOpen" class="schedule-group schedule-advanced-group">
        <div class="schedule-row">
          <span class="schedule-row-label">{{ tr('timezone') }}</span>
          <div class="schedule-row-control">
            <a-select
              :value="effectiveTimezone"
              class="schedule-borderless-select schedule-tz-select"
              :bordered="false"
              :disabled="disabled"
              show-search
              :dropdown-match-select-width="false"
              :options="timezoneOptions"
              :aria-label="tr('timezone')"
              @change="handleTimezoneChange"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.schedule-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  min-width: 0;
  color: var(--site-text-color, rgba(0, 0, 0, 0.88));
  font-size: 13px;
}

.schedule-group {
  display: flex;
  flex-direction: column;
  border: 1px solid color-mix(in srgb, var(--site-text-color, #000) 14%, transparent);
  border-radius: 10px;
  background: var(--component-background, #ffffff);
  overflow: hidden;
}

.schedule-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 40px;
  padding: 6px 12px;
  flex-wrap: wrap;
}

.schedule-row + .schedule-row {
  border-top: 1px solid color-mix(in srgb, var(--site-text-color, #000) 9%, transparent);
}

.schedule-row-label {
  color: var(--site-text-color, rgba(0, 0, 0, 0.88));
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
}

.schedule-row-control {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  min-width: 0;
  flex: 1 1 auto;
  text-align: right;
}

.schedule-borderless-select {
  min-width: 92px;
  text-align: right;
}

.schedule-borderless-select :deep(.ant-select-selector) {
  padding-right: 20px !important;
  padding-left: 6px !important;
}

.schedule-borderless-select :deep(.ant-select-selection-item) {
  text-align: right;
  font-weight: 500;
  color: var(--site-text-color, rgba(0, 0, 0, 0.88));
}

.schedule-interval-control {
  gap: 4px;
}

.schedule-interval-select {
  min-width: 68px;
}

.schedule-inline-input {
  height: 28px;
  padding: 2px 8px;
  border: 1px solid color-mix(in srgb, var(--site-text-color, #000) 15%, transparent);
  border-radius: 6px;
  background: transparent;
  color: var(--site-text-color, rgba(0, 0, 0, 0.88));
  font: inherit;
  font-weight: 500;
  text-align: right;
}

.schedule-inline-input:focus-visible {
  outline: 2px solid var(--color-primary, #1677ff);
  outline-offset: 1px;
}

.schedule-interval-number {
  width: 64px;
  font-variant-numeric: tabular-nums;
}

.schedule-date-input {
  width: auto;
  max-width: 150px;
  font-variant-numeric: tabular-nums;
}

.schedule-unit-suffix {
  color: var(--site-secondary-text-color, rgba(0, 0, 0, 0.55));
  font-size: 13px;
  white-space: nowrap;
}

.schedule-weekdays-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  max-width: 100%;
  padding: 4px 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--site-text-color, rgba(0, 0, 0, 0.88));
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  text-align: right;
}

.schedule-weekdays-trigger:hover:not(:disabled) {
  background: color-mix(in srgb, var(--site-text-color, #000) 6%, transparent);
}

.schedule-weekdays-trigger.is-invalid {
  color: #ff4d4f;
}

.schedule-weekdays-summary {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.schedule-weekdays-dropdown {
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--component-background, #ffffff);
  border: 1px solid color-mix(in srgb, var(--site-text-color, #000) 12%, transparent);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.14);
}

.schedule-weekdays-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.schedule-time-control {
  gap: 4px;
}

.schedule-tz-hint {
  color: var(--site-secondary-text-color, rgba(0, 0, 0, 0.55));
  font-size: 12px;
  white-space: nowrap;
}

.schedule-time-picker {
  width: 82px;
  padding: 2px 4px;
}

.schedule-time-picker :deep(input) {
  text-align: right;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  color: var(--site-text-color, rgba(0, 0, 0, 0.88));
}

.schedule-legacy-row {
  align-items: flex-start;
  background: color-mix(in srgb, var(--site-text-color, #000) 3%, transparent);
}

.schedule-legacy-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  text-align: left;
}

.schedule-legacy-title {
  font-weight: 600;
  font-size: 12px;
  word-break: break-all;
}

.schedule-legacy-hint {
  font-size: 11px;
  line-height: 1.45;
  color: var(--site-secondary-text-color, rgba(0, 0, 0, 0.58));
}

.schedule-validation-error {
  color: #ff4d4f;
  font-size: 12px;
  line-height: 1.4;
  padding: 0 4px;
}

.schedule-advanced {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.schedule-advanced-toggle {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--site-secondary-text-color, rgba(0, 0, 0, 0.58));
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.schedule-advanced-toggle:hover {
  color: var(--site-text-color, rgba(0, 0, 0, 0.88));
}

.schedule-advanced-chevron {
  transition: transform 0.18s ease;
}

.schedule-advanced-chevron.is-open {
  transform: rotate(180deg);
}

.schedule-tz-select {
  max-width: 100%;
}
</style>
