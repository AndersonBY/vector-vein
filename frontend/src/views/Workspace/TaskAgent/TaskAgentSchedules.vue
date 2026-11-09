<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { v4 as uuidv4 } from 'uuid'
import {
  Add,
  Calendar,
  Search,
  Control,
  Edit,
  Delete,
  PlayOne,
  Robot,
  FolderOpen,
  Time,
  OpenExternal,
  Setting, Refresh } from '@/icons'
import ScheduleEditor from '@/components/scheduling/ScheduleEditor.vue'
import ModelPicker from '@/components/ModelPicker.vue'
import AgentPicker from '@/components/taskAgent/AgentPicker.vue'
import TaskPicker from '@/components/taskAgent/TaskPicker.vue'
import TaskAgentPermissions from './TaskAgentPermissions.vue'
import TaskAgentModelError from './TaskAgentModelError.vue'
import { taskAgentAPI } from '@/api/taskAgent'
import { formatSchedule, getLocalTimezone } from '@/utils/schedule'
import { formatTaskTime } from '@/utils/taskAgentPresentation'
import { getChatModelOptions } from '@/utils/common'
import { validModelPair } from '@/utils/modelPreferences'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import { useUserSettingsStore } from '@/stores/userSettings'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const modelCatalog = useModelCatalogStore()
const settings = useUserSettingsStore()

const schedules = ref([])
const agents = ref([])
const projects = ref([])
const loading = ref(true)
const failed = ref(false)
const search = ref(String(route.query.search || ''))
const filter = computed(() =>
  ['enabled', 'disabled'].includes(route.query.filter) ? route.query.filter : 'all',
)

const togglingIds = reactive({})
const runningIds = reactive({})
const pendingRuns = reactive({})

const editorOpen = ref(false)
const editorSaving = ref(false)
const editorError = ref('')
const editorModelFailure = ref(null)
const scheduleValid = ref(true)
const editingTaskId = ref(null)
const originalExistingTaskId = ref(null)
const continuationSource = ref('automatic')
const targetTask = ref(null)
const targetLoading = ref(false)
const resolvedTargetId = ref(null)
const targetError = ref('')
let targetGeneration = 0
const editorBody = ref(null)

watch([editorOpen, editorError], ([open, error], [wasOpen]) => {
  if (open && (!wasOpen || error)) nextTick(() => { if (editorBody.value) editorBody.value.scrollTop = 0 })
})

const formState = reactive({
  schedule_id: '',
  expected_updated_at: '',
  name: '',
  goal: '',
  agent_id: 'general',
  project_id: '',
  run_mode: 'new',
  existing_task_id: null,
  model_provider: '',
  model: '',
  preference: 'default',
  reasoning_effort: 'default',
  permission_mode: 'auto',
  cron_expression: '0 9 * * *',
  recurrence: null,
  timezone: getLocalTimezone(),
  hide_after_run: false,
  notify_after_run: true,
  enabled: true,
})

const KNOWN_ERROR_CODES = new Set([
  'busy',
  'config_invalid',
  'project_unavailable',
  'task_missing',
  'connection_unavailable',
  'unknown',
  'changed',
  'disabled',
  'missed',
])

const tr = (key, params = {}) => t(`workspace.taskAgentSpace.scheduling.${key}`, params)

const resolveScheduleError = (response, fallbackKey = 'error_generic') => {
  const code =
    response?.data?.schedule_error?.code ||
    (typeof response?.data?.schedule_error === 'string' ? response.data.schedule_error : '') ||
    response?.data?.error_code ||
    (response?.status === 409 ? 'changed' : '')
  if (code && KNOWN_ERROR_CODES.has(code)) {
    return tr(`error_${code}`)
  }
  return tr(fallbackKey)
}

const modelOptions = computed(() => getChatModelOptions())

const projectOptions = computed(() => [
  { value: '', label: tr('project_none') },
  ...projects.value.map(p => ({
    value: p.project_id,
    label: p.name || p.title || p.project_id,
    disabled: Array.isArray(p.folders) && p.folders.some(f => !f.available),
  })),
])

const agentNameOf = agentId => {
  const found = agents.value.find(a => a.agent_id === agentId)
  if (found?.name) return found.name
  if (agentId === 'general') return t('workspace.taskAgentSpace.general_agent')
  return agentId || t('workspace.taskAgentSpace.general_agent')
}

const projectNameOf = projectId => {
  if (!projectId) return ''
  const found = projects.value.find(p => p.project_id === projectId)
  return found?.name || found?.title || projectId
}

const continueThreadLocked = computed(
  () => formState.run_mode === 'continue' && (continuationSource.value === 'existing' ||
    Boolean(formState.expected_updated_at && editingTaskId.value && !originalExistingTaskId.value)),
)

const loadExistingTask = async (tid, applyDefaults = true) => {
  const generation = ++targetGeneration
  formState.existing_task_id = tid || null
  resolvedTargetId.value = null
  targetTask.value = null
  targetError.value = ''
  if (!tid) { targetLoading.value = false; return }
  targetLoading.value = true
  try {
    const response = await taskAgentAPI('get', { task_id: tid, cached: true })
    if (!alive || generation !== targetGeneration || !editorOpen.value || formState.existing_task_id !== tid ||
      formState.run_mode !== 'continue' || continuationSource.value !== 'existing') return
    const task = response.data?.task
    if (response.status !== 200 || !task || task.tid !== tid) throw new Error()
    targetTask.value = task
    resolvedTargetId.value = tid
    formState.project_id = task.project_id || ''
    formState.agent_id = task.config_snapshot?.agent_profile?.agent_id || 'general'
    if (applyDefaults) {
      if (!formState.goal.trim()) formState.goal = task.goal || ''
      const current = response.data.runtime_settings || task
      formState.model_provider = current.model_provider || task.model_provider
      formState.model = current.model || task.model
      formState.reasoning_effort = current.reasoning_effort || 'default'
      formState.permission_mode = current.permission_mode || task.config_snapshot?.agent_profile?.permission_mode || 'auto'
      formState.preference = 'custom'
    }
  } catch { if (alive && generation === targetGeneration) targetError.value = tr('target_load_failed') }
  finally { if (alive && generation === targetGeneration) targetLoading.value = false }
}

const setContinuationSource = value => {
  continuationSource.value = value
  targetGeneration++
  targetError.value = ''
  targetLoading.value = false
  if (value === 'existing') {
    if (editingTaskId.value) loadExistingTask(editingTaskId.value)
  } else {
    formState.existing_task_id = null
    resolvedTargetId.value = null
    targetTask.value = null
  }
}

watch(() => formState.run_mode, value => {
  if (editorOpen.value && value === 'continue' && continuationSource.value === 'existing') {
    if (formState.existing_task_id) loadExistingTask(formState.existing_task_id, false)
  } else { targetGeneration++; targetLoading.value = false }
})

const isModelValid = computed(() =>
  validModelPair(modelOptions.value, formState.model_provider, formState.model),
)

const saveDisabled = computed(
  () =>
    editorSaving.value ||
    !String(formState.goal || '').trim() ||
    !String(formState.agent_id || '').trim() ||
    !isModelValid.value ||
    (formState.run_mode === 'continue' && continuationSource.value === 'existing' &&
      (!formState.existing_task_id || targetLoading.value || resolvedTargetId.value !== formState.existing_task_id)) ||
    !scheduleValid.value,
)

const filters = computed(() => [
  { key: 'all', label: tr('filter_all') },
  { key: 'enabled', label: tr('filter_enabled') },
  { key: 'disabled', label: tr('filter_disabled') },
])

const updateQuery = patch => {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  return router.replace({ name: 'taskAgentSchedules', query })
}

const filtered = computed(() => {
  const q = search.value.trim().toLocaleLowerCase()
  return schedules.value.filter(item => {
    if (filter.value === 'enabled' && !item.enabled) return false
    if (filter.value === 'disabled' && item.enabled) return false
    if (!q) return true
    const text = `${item.name || ''} ${item.goal || ''} ${item.model || ''} ${agentNameOf(item.agent_id)} ${projectNameOf(item.project_id)}`.toLocaleLowerCase()
    return text.includes(q)
  })
})

let alive = true
let loadGeneration = 0
let editorGeneration = 0
let pollTimer = null

const applyDefaultModelAndPermissions = (targetAgentId = 'general') => {
  const agent = agents.value.find(item => item.agent_id === targetAgentId)
  formState.permission_mode = agent?.permission_mode || 'auto'
  const preset =
    agent?.model_provider && agent?.model
      ? agent
      : settings.setting?.data?.model_preferences?.default
  if (
    (agent?.model_provider && agent?.model) ||
    validModelPair(modelOptions.value, preset?.model_provider, preset?.model)
  ) {
    formState.model_provider = preset.model_provider
    formState.model = preset.model
    formState.preference = agent?.model ? 'custom' : 'default'
    formState.reasoning_effort = preset.reasoning_effort || 'default'
  } else {
    const firstProvider = modelOptions.value[0]
    formState.model_provider = firstProvider?.value || ''
    formState.model = firstProvider?.children?.[0]?.value || ''
    formState.preference = 'custom'
    formState.reasoning_effort = 'default'
  }
}

const handleAgentSelect = nextAgentId => {
  formState.agent_id = nextAgentId
  applyDefaultModelAndPermissions(nextAgentId)
}

const load = async (quiet = false) => {
  clearTimeout(pollTimer)
  const gen = ++loadGeneration
  if (quiet !== true) loading.value = true
  failed.value = false
  try {
    const [schedRes, profRes, projRes] = await Promise.all([
      taskAgentAPI('schedules', {}),
      taskAgentAPI('profiles', {}),
      taskAgentAPI('projects', {}),
    ])
    if (!alive || gen !== loadGeneration) return
    if (schedRes?.status !== 200 || !Array.isArray(schedRes.data?.schedules)) {
      throw new Error('schedules_load_failed')
    }
    schedules.value = schedRes.data.schedules
    if (profRes?.status === 200 && Array.isArray(profRes.data?.agents)) {
      agents.value = profRes.data.agents
    }
    if (projRes?.status === 200 && Array.isArray(projRes.data?.projects)) {
      projects.value = projRes.data.projects
    }
  } catch {
    if (alive && gen === loadGeneration) {
      failed.value = true
    }
  } finally {
    if (alive && gen === loadGeneration) {
      loading.value = false
      pollTimer = setTimeout(() => load(true), 5000)
    }
  }
}
const replaceScheduleInList = record => {
  if (!record?.schedule_id) return
  const idx = schedules.value.findIndex(item => item.schedule_id === record.schedule_id)
  if (idx >= 0) {
    schedules.value.splice(idx, 1, record)
  } else {
    schedules.value.unshift(record)
  }
}

const openCreateModal = () => {
  editorGeneration++
  editorSaving.value = false
  editorError.value = ''
  editorModelFailure.value = null
  scheduleValid.value = true
  editingTaskId.value = null
  originalExistingTaskId.value = null
  continuationSource.value = 'automatic'
  targetGeneration++
  targetTask.value = null; targetError.value = ''; targetLoading.value = false
  resolvedTargetId.value = null

  formState.schedule_id = `sched_${uuidv4().replaceAll('-', '')}`
  formState.expected_updated_at = ''
  formState.name = ''
  formState.goal = ''
  formState.agent_id = 'general'
  formState.project_id = ''
  formState.run_mode = 'new'
  formState.existing_task_id = null
  formState.cron_expression = '0 9 * * *'
  formState.recurrence = null
  formState.timezone = getLocalTimezone()
  formState.hide_after_run = false
  formState.notify_after_run = true
  formState.enabled = true
  applyDefaultModelAndPermissions('general')

  editorOpen.value = true
}

const openEditModal = record => {
  if (!record?.schedule_id) return
  editorGeneration++
  editorSaving.value = false
  editorError.value = ''
  editorModelFailure.value = null
  scheduleValid.value = true
  editingTaskId.value = record.task_id || null
  originalExistingTaskId.value = record.existing_task_id || null
  continuationSource.value = record.existing_task_id ? 'existing' : 'automatic'
  targetGeneration++
  targetTask.value = null; targetError.value = ''; targetLoading.value = false
  resolvedTargetId.value = null

  formState.schedule_id = record.schedule_id
  formState.expected_updated_at = record.updated_at || ''
  formState.name = record.name || ''
  formState.goal = record.goal || ''
  formState.agent_id = record.agent_id || 'general'
  formState.project_id = record.project_id || ''
  formState.run_mode = record.run_mode === 'continue' ? 'continue' : 'new'
  formState.existing_task_id = record.existing_task_id || null
  formState.model_provider = record.model_provider || ''
  formState.model = record.model || ''
  formState.preference = 'custom'
  formState.reasoning_effort = record.reasoning_effort || 'default'
  formState.permission_mode = record.permission_mode || 'auto'
  formState.cron_expression = record.cron_expression || '0 9 * * *'
  formState.recurrence = record.recurrence ? { ...record.recurrence } : null
  formState.timezone = record.timezone || getLocalTimezone()
  formState.hide_after_run = Boolean(record.hide_after_run)
  formState.notify_after_run = record.notify_after_run !== false
  formState.enabled = record.enabled !== false

  editorOpen.value = true
  if (formState.existing_task_id) loadExistingTask(formState.existing_task_id, false)
}

const buildSavePayload = source => {
  const payload = {
    schedule_id: source.schedule_id,
    name: String(source.name || '').trim(),
    goal: String(source.goal || '').trim(),
    agent_id: source.agent_id || 'general',
    project_id: source.project_id ? String(source.project_id) : null,
    run_mode: source.run_mode === 'continue' ? 'continue' : 'new',
    existing_task_id: source.run_mode === 'continue' ? source.existing_task_id || null : null,
    model_provider: source.model_provider,
    model: source.model,
    reasoning_effort: source.reasoning_effort || 'default',
    permission_mode: source.permission_mode || 'auto',
    cron_expression: String(source.cron_expression || '').trim(),
    recurrence: source.recurrence ? { ...source.recurrence } : null,
    timezone: source.timezone || getLocalTimezone(),
    hide_after_run: Boolean(source.hide_after_run),
    notify_after_run: Boolean(source.notify_after_run),
    enabled: Boolean(source.enabled),
  }
  if (source.expected_updated_at) {
    payload.expected_updated_at = source.expected_updated_at
  }
  return payload
}

const submitScheduleEditor = async () => {
  if (saveDisabled.value) return false
  const reqGen = ++editorGeneration
  const targetId = formState.schedule_id
  const payload = buildSavePayload(formState)
  editorSaving.value = true
  editorError.value = ''
  editorModelFailure.value = null
  try {
    const response = await taskAgentAPI('save_schedule', payload)
    if (!alive || reqGen !== editorGeneration || !editorOpen.value || formState.schedule_id !== targetId) {
      return false
    }
    if (response?.status !== 200 || !response.data?.schedule_id) {
      editorModelFailure.value = response?.data?.model_failure || null
      editorError.value = resolveScheduleError(response, 'save_failed')
      if (response?.status === 409) {
        await load()
        const refreshed = schedules.value.find(s => s.schedule_id === targetId)
        if (refreshed?.updated_at) {
          formState.expected_updated_at = refreshed.updated_at
          editingTaskId.value = refreshed.task_id || null
        }
      }
      return false
    }
    replaceScheduleInList(response.data)
    editorOpen.value = false
    message.success(tr('saved'))
    return true
  } catch {
    if (alive && reqGen === editorGeneration && editorOpen.value && formState.schedule_id === targetId) {
      editorError.value = tr('save_failed')
    }
    return false
  } finally {
    if (alive && reqGen === editorGeneration) {
      editorSaving.value = false
    }
  }
}

const toggleScheduleEnabled = async (record, nextEnabled) => {
  const sid = record?.schedule_id
  if (!sid || togglingIds[sid]) return
  togglingIds[sid] = true
  try {
    const payload = buildSavePayload({
      ...record,
      expected_updated_at: record.updated_at,
      enabled: Boolean(nextEnabled),
    })
    const response = await taskAgentAPI('save_schedule', payload)
    if (!alive) return
    if (response?.status !== 200 || !response.data?.schedule_id) {
      message.error(resolveScheduleError(response, 'save_failed'))
      if (response?.status === 409) await load()
      return
    }
    replaceScheduleInList(response.data)
  } catch {
    if (alive) message.error(tr('save_failed'))
  } finally {
    if (alive) delete togglingIds[sid]
  }
}

const runScheduleNow = async record => {
  const sid = record?.schedule_id
  if (!sid || !record.updated_at || runningIds[sid]) return
  const inputId = pendingRuns[sid] || `run_${uuidv4().replaceAll('-', '')}`
  pendingRuns[sid] = inputId
  runningIds[sid] = true
  try {
    const response = await taskAgentAPI('run_schedule', {
      schedule_id: sid,
      input_id: inputId,
    })
    if (!alive) return
    if (response?.status === 200 && response.data?.run_id) {
      delete pendingRuns[sid]
      message.success(tr('run_now_triggered'))
      await load()
      return
    }
    if (response && [400, 404, 409].includes(response.status)) {
      delete pendingRuns[sid]
    }
    message.error(resolveScheduleError(response, 'run_failed'))
    if (response?.status === 409) await load()
  } catch {
    if (alive) {
      message.error(tr('error_connection_unavailable'))
    }
  } finally {
    if (alive) delete runningIds[sid]
  }
}

const confirmDeleteSchedule = record => {
  if (!record?.schedule_id) return
  const target = {
    schedule_id: record.schedule_id,
    expected_updated_at: record.updated_at,
    name: record.name || record.goal || record.schedule_id,
  }
  Modal.confirm({
    title: tr('delete_title', { name: target.name }),
    content: tr('delete_confirm'),
    okText: tr('delete'),
    cancelText: t('common.cancel'),
    okType: 'danger',
    async onOk() {
      try {
        const response = await taskAgentAPI('delete_schedule', {
          schedule_id: target.schedule_id,
          expected_updated_at: target.expected_updated_at,
        })
        if (!alive) return
        if (response?.status !== 200) {
          message.error(resolveScheduleError(response, 'delete_failed'))
          if (response?.status === 409) await load()
          return Promise.reject(new Error('delete_failed'))
        }
        delete pendingRuns[target.schedule_id]
        schedules.value = schedules.value.filter(item => item.schedule_id !== target.schedule_id)
        message.success(tr('deleted'))
      } catch (err) {
        if (err?.message !== 'delete_failed' && alive) {
          message.error(tr('delete_failed'))
        }
        return Promise.reject(err)
      }
    },
  })
}

const retryRun = async record => {
  const sid = record.schedule_id
  if (runningIds[sid] || record.last_run?.status !== 'UNKNOWN') return
  runningIds[sid] = true
  try {
    const response = await taskAgentAPI('retry_schedule_run', { schedule_id: sid, run_id: record.last_run.run_id })
    if (!alive) return
    if (response.status !== 200) { message.error(resolveScheduleError(response, 'run_failed')); return }
    message.success(tr('run_now_triggered'))
    await load(true)
  } catch { if (alive) message.error(tr('error_connection_unavailable')) }
  finally { if (alive) delete runningIds[sid] }
}

const openTaskDetail = taskId => {
  if (!taskId) return
  router.push({ name: 'taskAgentDetail', params: { taskId } })
}

const lastRunStatusClass = status => {
  if (status === 'COMPLETED') return 'is-completed'
  if (status === 'RUNNING' || status === 'ADMITTED') return 'is-running'
  if (status === 'FAILED') return 'is-failed'
  if (status === 'SKIPPED' || status === 'UNKNOWN' || status === 'INTERRUPTED') return 'is-attention'
  return ''
}

watch(
  () => route.query.search,
  val => {
    search.value = String(val || '')
  },
)

onMounted(() => {
  modelCatalog.ensureLoaded?.()
  load()
})

onBeforeUnmount(() => {
  alive = false
  clearTimeout(pollTimer)
  targetGeneration++
  loadGeneration++
  editorGeneration++
})

defineExpose({
  schedules,
  agents,
  projects,
  loading,
  failed,
  search,
  editorOpen,
  editorSaving,
  editorError,
  editorModelFailure,
  scheduleValid,
  formState,
  continueThreadLocked,
  saveDisabled,
  pendingRuns,
  load,
  openCreateModal,
  openEditModal,
  handleAgentSelect,
  submitScheduleEditor,
  toggleScheduleEnabled,
  runScheduleNow,
  retryRun,
  continuationSource,
  targetTask,
  targetError,
  targetLoading,
  loadExistingTask,
  setContinuationSource,
  confirmDeleteSchedule,
})
</script>
<template>
  <main class="schedules-catalog">
    <header class="catalog-header">
      <div class="catalog-title">
        <h1>{{ tr('title') }}</h1>
        <span>{{ tr('total_count', { count: schedules.length }) }}</span>
      </div>
      <div class="header-actions">
        <IconButton type="primary" class="create-schedule-btn" @click="openCreateModal" :text="tr('create')"><template #icon><Add /></template></IconButton>
      </div>
    </header>

    <div class="catalog-toolbar">
      <a-input
        v-model:value="search"
        class="catalog-search"
        allow-clear
        :aria-label="tr('search_placeholder')"
        :placeholder="tr('search_placeholder')"
        @change="updateQuery({ search: search.trim() || undefined })"
      >
        <template #prefix><Search /></template>
      </a-input>
      <div class="toolbar-actions">
        <a-dropdown :trigger="['click']">
          <IconButton type="text" class="toolbar-icon-btn" :class="{ 'filter-active': filter !== 'all' }" :aria-label="tr('filter_' + filter)" :text="tr('filter_' + filter)"><template #icon><Control /></template></IconButton>
          <template #overlay>
            <a-menu :selected-keys="[filter]" :items="filters" @click="({ key }) => updateQuery({ filter: key === 'all' ? undefined : key })" />
          </template>
        </a-dropdown>
      </div>
    </div>

    <section class="catalog-content" :aria-busy="loading">
      <a-alert
        v-if="failed"
        type="warning"
        show-icon
        :message="tr('load_failed')"
        class="load-alert"
      >
        <template #action>
          <IconButton size="small" @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
        </template>
      </a-alert>

      <div v-if="loading && !schedules.length" class="catalog-loading">
        <a-spin />
      </div>

      <template v-else>
        <div v-if="filtered.length" class="schedule-grid">
          <article
            v-for="item in filtered"
            :key="item.schedule_id"
            class="schedule-card"
            :class="{ 'is-disabled': !item.enabled }"
          >
            <div class="card-top">
              <div class="schedule-icon">
                <Calendar :size="20" />
              </div>
              <div class="card-copy">
                <div class="card-heading">
                  <h2 :title="item.name || item.goal">{{ item.name || item.goal }}</h2>
                  <span class="mode-badge">
                    {{ tr(item.run_mode === 'continue' ? 'continue_thread_badge' : 'new_thread_badge') }}
                  </span>
                </div>
                <p class="schedule-goal" :title="item.goal">{{ item.goal }}</p>
              </div>
              <a-switch
                :checked="Boolean(item.enabled)"
                size="small"
                :loading="Boolean(togglingIds[item.schedule_id])"
                :aria-label="tr('enable_aria', { name: item.name || item.schedule_id })"
                @change="checked => toggleScheduleEnabled(item, checked)"
              />
            </div>

            <div class="schedule-pattern-row">
              <span class="pattern-summary">{{ formatSchedule(item.cron_expression, item.recurrence, t) }}</span>
              <span class="pattern-tz">{{ item.timezone }}</span>
            </div>

            <div class="card-meta">
              <span class="meta-chip">
                <Robot />
                {{ agentNameOf(item.agent_id) }}
              </span>
              <span v-if="item.project_id" class="meta-chip">
                <FolderOpen />
                {{ projectNameOf(item.project_id) }}
              </span>
              <span v-if="item.model" class="meta-chip model-chip">
                {{ item.model }}
              </span>
            </div>

            <div class="schedule-runs-info">
              <div class="run-info-line">
                <span class="run-info-label">{{ tr('next_run') }}</span>
                <time v-if="item.enabled && item.next_run_at" :datetime="item.next_run_at">
                  <Time />
                  {{ formatTaskTime(item.next_run_at, locale) }}
                </time>
                <span v-else class="run-info-muted">{{ tr('next_run_none') }}</span>
              </div>

              <div class="run-info-line">
                <span class="run-info-label">{{ tr('last_run') }}</span>
                <div v-if="item.last_run" class="last-run-detail">
                  <span class="run-status-pill" :class="lastRunStatusClass(item.last_run.status)">
                    {{ tr(`status_${item.last_run.status}`) }}
                  </span>
                  <time v-if="item.last_run.scheduled_at" :datetime="item.last_run.scheduled_at">
                    {{ formatTaskTime(item.last_run.scheduled_at, locale) }}
                  </time>
                  <IconButton
                    v-if="item.last_run.task_id"
                    class="task-link-btn"
                    @click="openTaskDetail(item.last_run.task_id)"
                   size="small" :text="tr('open_last_task')"><template #icon><OpenExternal /></template></IconButton>
                </div>
                <span v-else class="run-info-muted">{{ tr('last_run_none') }}</span>
              </div>

              <div v-if="item.last_run?.error_code" class="run-error-note" role="status">
                {{ KNOWN_ERROR_CODES.has(item.last_run.error_code) ? tr(`error_${item.last_run.error_code}`) : tr('error_generic') }}
              </div>
            </div>

            <footer class="card-footer">
              <div class="footer-links">
                <IconButton
                  v-if="item.task_id && item.run_mode === 'continue'"
                  class="task-link-btn"
                  @click="openTaskDetail(item.task_id)"
                 size="small" :text="tr('open_task')"><template #icon><OpenExternal /></template></IconButton>
              </div>
              <div class="card-actions">
                <IconButton v-if="item.last_run?.status === 'UNKNOWN'" type="text" size="small" :loading="Boolean(runningIds[item.schedule_id])" @click="retryRun(item)" :text="tr('retry_run')"><template #icon><Refresh /></template></IconButton>
                <IconButton
                    type="text"
                    size="small"
                    class="run-now-btn"
                    :loading="Boolean(runningIds[item.schedule_id])"
                    :disabled="!item.enabled || item.last_run?.status === 'UNKNOWN' || Boolean(runningIds[item.schedule_id])"
                    :aria-label="pendingRuns[item.schedule_id] ? tr('run_uncertain_retry') : tr('run_now')"
                    @click="runScheduleNow(item)"
                   :text="pendingRuns[item.schedule_id] ? tr('run_uncertain_retry') : tr('run_now')"><template #icon><PlayOne /></template></IconButton>
                <IconButton
                    type="text"
                    size="small"
                    :aria-label="tr('edit')"
                    @click="openEditModal(item)"
                   :text="tr('edit')"><template #icon><Edit /></template></IconButton>
                <IconButton
                    type="text"
                    size="small"
                    danger
                    :aria-label="tr('delete')"
                    @click="confirmDeleteSchedule(item)"
                   :text="tr('delete')"><template #icon><Delete /></template></IconButton>
              </div>
            </footer>
          </article>
        </div>

        <div v-else class="empty-state">
          <a-empty :description="tr('empty_title')">
            <p class="empty-hint">{{ tr('empty_description') }}</p>
            <a-button type="primary" @click="openCreateModal">
              <template #icon><Add /></template>
              {{ tr('create') }}
            </a-button>
          </a-empty>
        </div>
      </template>
    </section>

    <a-modal
      v-model:open="editorOpen"
      :title="formState.expected_updated_at ? tr('edit') : tr('create')"
      :width="640"
      :ok-text="tr('save')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="editorSaving"
      :ok-button-props="{ disabled: saveDisabled }"
      :cancel-button-props="{ disabled: editorSaving }"
      :mask-closable="!editorSaving"
      :closable="!editorSaving"
      :keyboard="!editorSaving"
      @ok="submitScheduleEditor"
    >
      <div ref="editorBody" class="schedule-modal-body">
        <a-alert
          v-if="editorError"
          type="error"
          show-icon
          class="modal-alert"
          :message="editorError"
        />
        <TaskAgentModelError
          v-if="editorModelFailure"
          :failure="editorModelFailure"
          :model-config="{ selected_model: formState.model }"
          class="modal-alert"
        />

        <a-form layout="vertical" class="schedule-form">
          <a-form-item :label="tr('name_label')">
            <a-input
              v-model:value="formState.name"
              :aria-label="tr('name_label')"
              :disabled="editorSaving"
              :maxlength="160"
              :placeholder="tr('name_placeholder')"
            />
          </a-form-item>

          <a-form-item :label="tr('goal_label')" required>
            <a-textarea
              v-model:value="formState.goal"
              :aria-label="tr('goal_label')"
              :disabled="editorSaving"
              :auto-size="{ minRows: 3, maxRows: 7 }"
              :placeholder="tr('goal_placeholder')"
            />
          </a-form-item>

          <div class="form-two-col">
            <a-form-item :label="tr('agent_label')" required>
              <AgentPicker
                :model-value="formState.agent_id"
                :agents="agents"
                :disabled="editorSaving || continueThreadLocked"
                @change="handleAgentSelect"
              />
            </a-form-item>

            <a-form-item :label="tr('project_label')">
              <a-select
                v-model:value="formState.project_id"
                :options="projectOptions"
                :disabled="editorSaving || continueThreadLocked"
                :aria-label="tr('project_label')"
              />
            </a-form-item>
          </div>

          <p v-if="continueThreadLocked && continuationSource === 'automatic'" class="form-field-note is-warning">
            {{ tr('continue_locked_hint') }}
          </p>

          <a-form-item :label="tr('run_mode_label')">
            <a-radio-group
              v-model:value="formState.run_mode"
              :disabled="editorSaving"
              class="run-mode-group"
            >
              <a-radio value="new">{{ tr('run_mode_new') }}</a-radio>
              <a-radio value="continue">{{ tr('run_mode_continue') }}</a-radio>
            </a-radio-group>
            <p class="form-field-note">
              {{ tr(formState.run_mode === 'continue' ? (continuationSource === 'existing' ? 'target_inherit_hint' : 'run_mode_continue_hint') : 'run_mode_new_hint') }}
            </p>
          </a-form-item>

          <a-form-item v-if="formState.run_mode === 'continue'" :label="tr('continuation_target')">
            <a-radio-group :value="continuationSource" :disabled="editorSaving" @change="setContinuationSource($event.target.value)">
              <a-radio value="automatic">{{ tr('target_automatic') }}</a-radio>
              <a-radio value="existing">{{ tr('target_existing') }}</a-radio>
            </a-radio-group>
            <template v-if="continuationSource === 'existing'">
              <TaskPicker :model-value="formState.existing_task_id || ''" :selected-task="targetTask" allow-clear
                :disabled="editorSaving" :placeholder="tr('target_placeholder')" style="margin-top: 12px"
                @change="tid => loadExistingTask(tid)" />
              <a-spin v-if="targetLoading" size="small" />
              <p class="form-field-note">{{ tr('target_inherit_hint') }}</p>
              <div v-if="targetError" role="alert"><a-typography-text type="danger">{{ targetError }}</a-typography-text><IconButton size="small" @click="loadExistingTask(formState.existing_task_id, false)" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></div>
            </template>
            <p v-else class="form-field-note">{{ tr('target_automatic_hint') }}</p>
          </a-form-item>

          <div class="form-two-col">
            <a-form-item :label="tr('model_label')" required>
              <div class="picker-box">
                <ModelPicker
                  v-model:model="formState.model"
                  v-model:model-provider="formState.model_provider"
                  v-model:preference="formState.preference"
                  v-model:reasoning-effort="formState.reasoning_effort"
                  :options="modelOptions"
                  :disabled="editorSaving"
                />
              </div>
            </a-form-item>

            <a-form-item :label="tr('permission_label')">
              <div class="picker-box">
                <TaskAgentPermissions
                  v-model="formState.permission_mode"
                  :disabled="editorSaving"
                />
              </div>
            </a-form-item>
          </div>

          <a-form-item :label="tr('schedule_label')" required>
            <ScheduleEditor
              v-if="editorOpen"
              v-model="formState.cron_expression"
              v-model:recurrence="formState.recurrence"
              v-model:timezone="formState.timezone"
              :disabled="editorSaving"
              @validity-change="scheduleValid = $event"
            />
          </a-form-item>

          <div class="schedule-switches">
            <div class="switch-row">
              <div class="switch-copy">
                <strong>{{ tr('enabled') }}</strong>
              </div>
              <a-switch v-model:checked="formState.enabled" :disabled="editorSaving" :aria-label="tr('enabled')" />
            </div>

            <div class="switch-row">
              <div class="switch-copy">
                <strong>{{ tr('hide_after_run') }}</strong>
                <small>{{ tr('hide_after_run_hint') }}</small>
              </div>
              <a-switch v-model:checked="formState.hide_after_run" :disabled="editorSaving" :aria-label="tr('hide_after_run')" />
            </div>

            <div class="switch-row">
              <div class="switch-copy">
                <div class="switch-title-inline">
                  <strong>{{ tr('notify_after_run') }}</strong>
                  <router-link
                    :to="{ name: 'settings', query: { section: 'notifications' } }"
                    class="settings-link"
                    @click="editorOpen = false"
                  >
                    <Setting :size="12" />
                    <span>{{ tr('notifications_settings_link') }}</span>
                  </router-link>
                </div>
                <small>{{ tr('notify_after_run_hint') }}</small>
              </div>
              <a-switch v-model:checked="formState.notify_after_run" :disabled="editorSaving" :aria-label="tr('notify_after_run')" />
            </div>
          </div>

          <p class="runtime-help-note">{{ tr('runtime_notice') }}</p>
        </a-form>
      </div>
    </a-modal>
  </main>
</template>
<style scoped>
.schedules-catalog {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-width: 0;
  color: var(--site-text-color);
}

.catalog-header {
  min-height: 52px;
  padding: 6px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: var(--light-border);
  background: var(--component-background);
  flex-shrink: 0;
}

.catalog-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.catalog-title > span {
  font-size: 12px;
  color: var(--site-secondary-text-color);
  font-variant-numeric: tabular-nums;
}

.catalog-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 52px;
  padding: 8px 24px;
  background: var(--component-background);
  border-bottom: var(--light-border);
  flex-shrink: 0;
}

.catalog-search {
  width: 320px;
  max-width: 55%;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

:deep(.toolbar-icon-btn) {
  color: var(--site-secondary-text-color);
}

:deep(.toolbar-icon-btn).filter-active {
  color: var(--color-primary);
}

.catalog-content {
  background: var(--gray-background);
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px 24px 24px;
}

.load-alert {
  margin-bottom: 12px;
}

.catalog-loading {
  display: grid;
  place-items: center;
  min-height: 220px;
}

.schedule-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
}

.schedule-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid color-mix(in srgb, var(--site-text-color) 7%, transparent);
  border-radius: 8px;
  background: var(--component-background);
  min-width: 0;
}

.schedule-card.is-disabled {
  opacity: 0.72;
}

.card-top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.schedule-icon {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  border: var(--light-border);
  background: color-mix(in srgb, var(--color-primary) 8%, var(--component-background));
  color: var(--color-primary);
}

.card-copy {
  min-width: 0;
  flex: 1;
}

.card-heading {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mode-badge {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--gray-background);
  color: var(--site-secondary-text-color);
  font-size: 11px;
}

.schedule-goal {
  margin: 3px 0 0;
  font-size: 12px;
  line-height: 1.55;
  color: var(--site-secondary-text-color);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.schedule-pattern-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--gray-background);
  font-size: 12px;
}

.pattern-summary {
  font-weight: 500;
  color: var(--site-text-color);
}

.pattern-tz {
  font-size: 11px;
  color: var(--site-secondary-text-color);
  white-space: nowrap;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  color: var(--site-secondary-text-color);
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.schedule-runs-info {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-top: 6px;
  border-top: var(--light-border);
  font-size: 12px;
}

.run-info-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.run-info-label {
  color: var(--site-secondary-text-color);
  white-space: nowrap;
}

.run-info-line time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-variant-numeric: tabular-nums;
  color: var(--site-text-color);
}

.run-info-muted {
  color: var(--site-secondary-text-color);
}

.last-run-detail {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.run-status-pill {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: var(--gray-background);
  color: var(--site-secondary-text-color);
}

.run-status-pill.is-completed {
  color: #3c7c40;
  background: #edf7ed;
}

.run-status-pill.is-running {
  color: #167d91;
  background: #e9f7fa;
}

.run-status-pill.is-failed {
  color: #b4453c;
  background: #fff0ed;
}

.run-status-pill.is-attention {
  color: #9a6700;
  background: #fff5dc;
}

.run-error-note {
  font-size: 11px;
  color: #cf1322;
  line-height: 1.4;
}

:deep(.task-link-btn) {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

:deep(.task-link-btn):hover {
  text-decoration: underline;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 6px;
  border-top: var(--light-border);
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
}

.empty-state {
  display: grid;
  place-items: center;
  min-height: 280px;
  padding: 32px 16px;
}

.empty-hint {
  margin: 4px 0 14px;
  font-size: 12px;
  color: var(--site-secondary-text-color);
}

.schedule-modal-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 72vh;
  overflow-y: auto;
  padding-right: 4px;
}

.modal-alert {
  margin-bottom: 8px;
}

.form-two-col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.picker-box {
  display: flex;
  align-items: center;
  min-height: 34px;
  padding: 2px 8px;
  border: var(--light-border);
  border-radius: 6px;
  background: var(--component-background);
}

.run-mode-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.form-field-note {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--site-secondary-text-color);
}

.form-field-note.is-warning {
  margin: -4px 0 12px;
  color: #d46b08;
}

.schedule-switches {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 12px;
  border: var(--light-border);
  border-radius: 8px;
  background: var(--gray-background);
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.switch-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.switch-copy strong {
  font-size: 13px;
  font-weight: 500;
}

.switch-copy small {
  font-size: 11px;
  color: var(--site-secondary-text-color);
}

.switch-title-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.settings-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-primary);
}

.runtime-help-note {
  margin: 12px 0 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--site-text-color) 4%, transparent);
  color: var(--site-secondary-text-color);
  font-size: 12px;
  line-height: 1.55;
}

@media (max-width: 680px) {
  .form-two-col {
    grid-template-columns: 1fr;
  }
}
</style>
