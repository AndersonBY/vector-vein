<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, inject, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { v4 as uuidv4 } from 'uuid'
import TextOutput from '@/components/TextOutput.vue'
import { Left, Send, PlayOne, HandleSquare, MenuUnfoldOne, Down, Robot, Time, ListOne, Refresh } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { taskStatusClass, formatTaskTime } from '@/utils/taskAgentPresentation'
import { isParkedMcpWait, mergeTaskTimeline, taskIsActive, taskNeedsPolling, taskFileLink } from '@/utils/taskAgentTimeline'
import TaskAgentTimeline from './TaskAgentTimeline.vue'
import TaskAgentInteraction from './TaskAgentInteraction.vue'
import TaskAgentWorkspace from './TaskAgentWorkspace.vue'
import TaskAgentWorkflowRuns from './TaskAgentWorkflowRuns.vue'
import TaskAgentPermissions from './TaskAgentPermissions.vue'
import TaskAgentContextUsage from './TaskAgentContextUsage.vue'
import TaskAgentModelError from './TaskAgentModelError.vue'
import ModelPicker from '@/components/ModelPicker.vue'
import { getChatModelOptions } from '@/utils/common'
import { useModelCatalogStore } from '@/stores/modelCatalog'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const detail = ref(null)
const modelCatalog = useModelCatalogStore()
const modelOptions = computed(() => getChatModelOptions())
const runtimeModel = ref(''), runtimeProvider = ref(''), runtimeEffort = ref('default'), runtimePreference = ref('custom')
const settingsSaving = ref(false), settingsError = ref(''), settingsModelFailure = ref(null), pendingSettings = ref(null)
let settingsGeneration = 0
const loading = ref(true)
const loadError = ref(false)
const notFound = ref(false)
const reply = ref('')
const busy = ref(false)
const pendingRequest = ref(null)
const following = ref(true)
const scroller = ref(null)
const workspace = ref(null)
const showWorkspace = ref(true)
const layout = ref(null)
const narrow = ref(false)
const resizing = ref(false)
const leftWidth = ref(40)
const cycleCount = computed(() => (detail.value?.timeline || []).reduce((max, entry) => Number.isFinite(entry.cycle) ? Math.max(max, entry.cycle) : max, 0))
const pendingTodos = computed(() => (detail.value?.todos || []).filter(todo => todo.status !== 'completed').length)
let mediaQuery = null
const updateNarrow = () => { narrow.value = Boolean(mediaQuery?.matches) }
const panelWidth = value => {
  const width = layout.value?.getBoundingClientRect?.().width || 1000
  const minimum = Math.max(20, Math.min(40, 320 / width * 100))
  const maximum = Math.min(80, Math.max(60, 100 - 320 / width * 100))
  leftWidth.value = Math.min(maximum, Math.max(minimum, value))
}
const savePanelWidth = () => { try { localStorage.setItem('task-agent-detail-left-width', String(leftWidth.value)) } catch { /* Storage is optional. */ } }
const startResize = event => { if (event.button !== 0) return; event.preventDefault(); resizing.value = true; event.currentTarget.setPointerCapture?.(event.pointerId) }
const resize = event => { if (!resizing.value) return; const bounds = layout.value.getBoundingClientRect(); panelWidth((event.clientX - bounds.left) / bounds.width * 100) }
const endResize = () => { resizing.value = false; savePanelWidth() }
const resizeKey = event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  panelWidth(event.key === 'Home' ? 20 : event.key === 'End' ? 80 : leftWidth.value + (event.key === 'ArrowLeft' ? -2 : 2))
  savePanelWidth()
}
onMounted(() => {
  try { const saved = Number(localStorage.getItem('task-agent-detail-left-width')); if (saved >= 20 && saved <= 80) panelWidth(saved) } catch { /* Storage is optional. */ }
  mediaQuery = window.matchMedia?.('(max-width: 900px)')
  updateNarrow()
  if (narrow.value) showWorkspace.value = false
  mediaQuery?.addEventListener?.('change', updateNarrow)
  modelCatalog.ensureLoaded?.()
})
const task = computed(() => detail.value?.task)
const projectContext = inject('taskAgentProjectContext', null)
watch(() => task.value?.project_id, value => { if (projectContext) projectContext.value = value || '' }, { immediate: true })
const backRoute = computed(() => task.value?.project_id ? { name: 'taskAgentProject', params: { projectId: task.value.project_id } } : { name: 'taskAgentTasks' })
const state = computed(() => detail.value?.state || {})
const runtimeSettings = computed(() => detail.value?.runtime_settings || {
  revision: 0, model_provider: task.value?.model_provider, model: task.value?.model,
  reasoning_effort: task.value?.reasoning_effort || 'default', context_length: task.value?.config_snapshot?.context_length,
  permission_mode: task.value?.config_snapshot?.agent_profile?.permission_mode || 'ask',
})
const syncError = computed(() => detail.value?.sync_error || loadError.value)
const starting = computed(() => Boolean(detail.value?.start_pending))
const active = computed(() => starting.value || taskIsActive(task.value?.status))
const workflowWaiting = computed(() => task.value?.status === 'WAITING_FOR_WORKFLOW')
const parkedMcpWaiting = computed(() => isParkedMcpWait(task.value, state.value, detail.value?.mcp_runs))
const showThinking = computed(() => active.value && !question.value && !workflowWaiting.value && !parkedMcpWaiting.value && !syncError.value && task.value?.status !== 'PAUSED')
const entries = computed(() => mergeTaskTimeline(detail.value?.messages, detail.value?.timeline).filter(entry => !(
  entry.kind === 'question' && entry.turn_id === state.value.pendingInteraction?.turnId && entry.text === state.value.pendingInteraction?.prompt
)))
const question = computed(() => {
  const current = state.value.pendingInteraction
  if (current?.kind !== 'approval') return current
  const timeline = detail.value?.timeline || []
  const entry = timeline.findLast(item => (
    item.kind === 'approval_requested'
    && item.request_id === current.requestId
    && (!current.turnId || item.turn_id === current.turnId)
  ))
  const targetTurnId = current.turnId || entry?.turn_id || task.value?.current_turn_id || ''
  const targetCallId = current.tool_call_id || current.toolCallId || entry?.tool_call_id || ''
  const isChildSession = Boolean(current.sessionId && task.value?.tid && current.sessionId !== task.value.tid)
  const tool = (!isChildSession && targetCallId && targetTurnId)
    ? timeline.findLast(item => item.kind === 'tool' && item.tool_call_id === targetCallId && item.turn_id === targetTurnId)
    : null
  const workflow = task.value?.config_snapshot?.workflow_tools?.find(item => item.tool_name === (current.tool_name || entry?.tool_name))
  const resolvedArgs = current.arguments !== undefined ? current.arguments : (tool?.arguments !== undefined ? tool.arguments : entry?.arguments)
  return { ...entry, ...current, permission_mode: runtimeSettings.value.permission_mode || task.value?.config_snapshot?.agent_profile?.permission_mode, tool_name: current.display_name || entry?.display_name || current.tool_name || entry?.tool_name, arguments: resolvedArgs, workflow }
})
const canSend = computed(() => Boolean(reply.value.trim()) && !active.value && !busy.value && !pendingRequest.value && !question.value && !workflowWaiting.value && !parkedMcpWaiting.value && !syncError.value && task.value?.status !== 'PAUSED')
let generation = 0
let timer = null
const id = () => uuidv4().replaceAll('-', '')
const stopPolling = () => { if (timer !== null) window.clearTimeout(timer); timer = null }
const scrollToLatest = async () => {
  following.value = true
  await nextTick()
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}
const onScroll = () => {
  const el = scroller.value
  following.value = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 100
}
const syncRuntimeSettings = value => {
  if (!value) return
  runtimeModel.value = value.model || ''
  runtimeProvider.value = value.model_provider || ''
  runtimeEffort.value = value.reasoning_effort || 'default'
  if (pendingSettings.value?.request_id === value.last_change_id) {
    pendingSettings.value = null; settingsError.value = ''; settingsModelFailure.value = null
  }
}
const apply = async value => {
  const current = detail.value?.runtime_settings
  if (current && (current.revision || 0) > (value.runtime_settings?.revision || 0)) value = { ...value, runtime_settings: current }
  detail.value = value
  syncRuntimeSettings(runtimeSettings.value)
  if (following.value) await scrollToLatest()
}
const schedulePolling = () => {
  stopPolling()
  if (busy.value || settingsSaving.value) return
  if (taskNeedsPolling(task.value?.status, syncError.value || state.value.history_pending) || pendingRequest.value || pendingSettings.value || runtimeSettings.value.pending_change_id) timer = window.setTimeout(() => loadTask(true), 1500)
}
const loadTask = async (background = false) => {
  if (background && busy.value) return
  const current = ++generation
  const taskId = route.params.taskId
  if (!background) loading.value = true
  try {
    const response = await taskAgentAPI('get', { task_id: taskId, cached: !background })
    if (current !== generation || taskId !== route.params.taskId) return
    notFound.value = response.status === 404
    if (response.status !== 200) throw new Error()
    loadError.value = false
    await apply(response.data)
  } catch { if (current === generation) loadError.value = true }
  finally {
    if (current === generation) {
      loading.value = false
      if (!notFound.value) {
        if (!background && !loadError.value) loadTask(true)
        else schedulePolling()
      }
    }
  }
}
const submit = async (action, payload) => {
  if (busy.value || starting.value) return
  const taskId = route.params.taskId
  const current = ++generation
  stopPolling()
  busy.value = true
  pendingRequest.value = { action, payload }
  try {
    const response = await taskAgentAPI(action, payload)
    if (current !== generation || taskId !== route.params.taskId) return
    if (response.status !== 200) {
      if ([400, 404, 409].includes(response.status)) pendingRequest.value = null
      message.error(t(response.status === 409 ? 'workspace.taskAgentSpace.task_changed' : 'workspace.taskAgentSpace.request_failed'))
      return
    }
    pendingRequest.value = null
    if (action === 'send_message') reply.value = ''
    following.value = true
    await apply(response.data)
  } catch { if (current === generation) message.error(t('workspace.taskAgentSpace.request_failed')) }
  finally { if (current === generation) { busy.value = false; schedulePolling() } }
}
const sendMessage = () => { if (canSend.value) submit('send_message', { task_id: task.value.tid, input_id: id(), text: reply.value.trim() }) }
const takeAction = action => submit('action', { task_id: task.value.tid, turn_id: task.value.current_turn_id, action_id: id(), action })
const approve = decision => submit('approval', { task_id: task.value.tid, turn_id: task.value.current_turn_id, request_id: question.value.requestId, decision })
const retryRequest = () => { const pending = pendingRequest.value; if (pending) submit(pending.action, pending.payload) }
const submitSettings = async payload => {
  if (settingsSaving.value) return false
  const taskId = route.params.taskId, request = ++settingsGeneration
  settingsSaving.value = true; settingsError.value = ''; settingsModelFailure.value = null
  try {
    const response = await taskAgentAPI('update_runtime_settings', payload)
    if (request !== settingsGeneration || taskId !== route.params.taskId) return false
    if (response.status !== 200) {
      if ([400, 404, 409].includes(response.status)) pendingSettings.value = null
      settingsModelFailure.value = response.data?.model_failure || null
      settingsError.value = t(response.status === 409 ? 'workspace.taskAgentSpace.task_changed' : pendingSettings.value ? 'workspace.taskAgentSpace.runtime_settings_uncertain' : 'workspace.taskAgentSpace.runtime_settings_failed')
      if (response.status === 409) await loadTask(true)
      return false
    }
    const incoming = response.data?.runtime_settings
    if (!incoming) throw new Error()
    if (detail.value && (incoming.revision || 0) >= (detail.value.runtime_settings?.revision || 0)) detail.value.runtime_settings = incoming
    syncRuntimeSettings(runtimeSettings.value)
    pendingSettings.value = null
    message.success(t(payload.permission_mode ? 'workspace.taskAgentSpace.runtime_settings_next_permission' : 'workspace.taskAgentSpace.runtime_settings_next_model'))
    return true
  } catch {
    if (request === settingsGeneration && taskId === route.params.taskId) settingsError.value = t('workspace.taskAgentSpace.runtime_settings_uncertain')
    return false
  } finally {
    if (request === settingsGeneration) { settingsSaving.value = false; schedulePolling() }
  }
}
const changeSettings = patch => {
  if (!task.value || settingsSaving.value) return Promise.resolve(false)
  if (pendingSettings.value) {
    if (Object.entries(patch).some(([key, value]) => pendingSettings.value[key] !== value)) {
      message.warning(t('workspace.taskAgentSpace.runtime_settings_uncertain'))
      return Promise.resolve(false)
    }
    return submitSettings(pendingSettings.value)
  }
  if (Object.entries(patch).every(([key, value]) => runtimeSettings.value[key] === value)) return Promise.resolve(true)
  const payload = { task_id: task.value.tid, request_id: id(), expected_revision: runtimeSettings.value.revision || 0, ...patch }
  pendingSettings.value = payload
  return submitSettings(payload)
}
const changeModel = selection => changeSettings({ model_provider: selection.model_provider, model: selection.model, reasoning_effort: selection.reasoning_effort || 'default' })
const changePermission = permission_mode => changeSettings({ permission_mode })
const retrySettings = () => { if (pendingSettings.value) return submitSettings(pendingSettings.value) }
const openWorkspaceContent = async (method, value) => {
  const taskId = task.value?.tid
  if (!taskId) return
  showWorkspace.value = true
  await nextTick()
  if (task.value?.tid === taskId) workspace.value?.[method](value)
}
const previewFile = path => openWorkspaceContent('showPreview', path)
const onFileLink = event => {
  const link = event.target.closest?.('a')
  if (!link || link.classList?.contains('snapshot-skill-link')) return
  const href = link.getAttribute('href') || ''
  const path = taskFileLink(href, Boolean(task.value?.config_snapshot?.project))
  if (path) {
    event.preventDefault(); event.stopPropagation()
    try { previewFile(decodeURIComponent(path)) } catch { message.error(t('workspace.taskAgentSpace.file_failed')) }
  }
}
const readResult = entry => openWorkspaceContent('openTool', entry)
const openSubtask = entry => openWorkspaceContent('openSubtask', entry)
const openPlan = () => openWorkspaceContent('launch', 'plan')
const openAgentSnapshot = () => openWorkspaceContent('launch', 'agent')
watch(() => route.params.taskId, () => {
  generation++; stopPolling()
  settingsGeneration++; settingsSaving.value = false; pendingSettings.value = null; settingsError.value = ''; settingsModelFailure.value = null
  detail.value = null; reply.value = ''; busy.value = false; pendingRequest.value = null
  loadError.value = false; notFound.value = false; following.value = true; resizing.value = false
  loadTask()
}, { immediate: true })
onBeforeUnmount(() => { generation++; settingsGeneration++; stopPolling(); if (projectContext) projectContext.value = ''; mediaQuery?.removeEventListener?.('change', updateNarrow) })
</script>

<template>
  <main ref="layout" class="task-detail-page" :class="{ 'is-resizing': resizing, 'workspace-visible': showWorkspace, 'narrow-layout': narrow }">
    <div v-show="!(narrow && showWorkspace)" class="task-conversation" :style="{ flexBasis: showWorkspace && !narrow ? leftWidth + '%' : '100%' }">
      <nav class="detail-breadcrumb" :aria-label="t('workspace.taskAgentSpace.task_detail')"><router-link :to="backRoute">{{ task?.config_snapshot?.project?.name || t('workspace.taskAgentSpace.tasks') }}</router-link><span aria-hidden="true">/</span><span>{{ t('workspace.taskAgentSpace.task_detail') }}</span></nav>
      <header class="detail-header">
        <IconButton type="text" :aria-label="t('workspace.taskAgentSpace.back_to_tasks')" @click="router.push(backRoute)" :text="t('workspace.taskAgentSpace.back_to_tasks')"><template #icon><Left /></template></IconButton>
        <div class="detail-heading"><h1 :title="task?.title">{{ task?.title || t('workspace.taskAgentSpace.task_detail') }}</h1></div>
        <span v-if="task" :class="['detail-status', taskStatusClass(task.status)]">{{ t(starting ? 'workspace.taskAgentSpace.starting' : 'workspace.taskAgentSpace.status_' + task.status) }}</span>
        <IconButton class="workspace-toggle" :aria-label="t('workspace.taskAgentSpace.toggle_workspace')" :aria-pressed="showWorkspace" @click="showWorkspace = !showWorkspace" size="small" :text="t('workspace.taskAgentSpace.toggle_workspace')"><template #icon><MenuUnfoldOne /><small v-if="pendingTodos">{{ pendingTodos }}</small></template></IconButton>
      </header>
      <div v-if="syncError && !notFound && !starting" class="sync-notice" role="status"><span>{{ t(task?.status === 'PENDING' ? 'workspace.taskAgentSpace.start_failed' : 'workspace.taskAgentSpace.sync_error') }}</span><IconButton @click="task?.status === 'PENDING' ? submit('retry_start', { task_id: task.tid }) : detail?.recovery_required ? submit('recover', { task_id: task.tid }) : loadTask()" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></div>
      <TaskAgentModelError v-if="detail?.start_model_failure" :failure="detail.start_model_failure" :model-config="task?.config_snapshot" />
      <div ref="scroller" class="detail-content" @scroll.passive="onScroll" @click.capture="onFileLink">
        <a-spin :spinning="loading">
          <div v-if="task" class="task-content">
            <div class="task-overview">
              <div class="overview-agent"><Robot /><span><small>{{ t('workspace.taskAgentSpace.agent') }}</small><strong>{{ task.config_snapshot?.agent_profile?.name || t('workspace.taskAgentSpace.general_agent') }}</strong></span></div>
              <button v-if="task.config_snapshot?.skills?.length" type="button" class="overview-capability-chip" @click="openAgentSnapshot">{{ t('workspace.taskAgentSpace.profile_skill_count', { count: task.config_snapshot.skills.length }) }}</button>
              <button v-if="task.config_snapshot?.mcp_tools?.length" type="button" class="overview-capability-chip" @click="openAgentSnapshot">{{ t('workspace.taskAgentSpace.profile_mcp_count', { count: task.config_snapshot.mcp_tools.length }) }}</button>
              <time v-if="task.created_at"><Time />{{ formatTaskTime(task.created_at, locale) }}</time>
              <span class="overview-cycles" :title="t('workspace.taskAgentSpace.max_cycles')">{{ task.config_snapshot?.agent_profile?.max_cycles > 0 ? t('workspace.taskAgentSpace.cycles', { count: cycleCount, max: task.config_snapshot.agent_profile.max_cycles }) : t('workspace.taskAgentSpace.cycles_unlimited', { count: cycleCount }) }}</span>
              <button v-if="detail.todos?.length" type="button" @click="openPlan"><ListOne />{{ t('workspace.taskAgentSpace.plan') }} {{ detail.todos.filter(todo => todo.status === 'completed').length }}/{{ detail.todos.length }}</button>
            </div>
            <div v-if="task.config_snapshot?.knowledge_bases?.length" class="task-knowledge-mounts"><strong>{{ t('knowledgeBase.mounted') }}</strong><a-space wrap><router-link v-for="base in task.config_snapshot.knowledge_bases" :key="base.kb_id" :to="{ name: 'KnowledgeBaseDetail', params: { kbId: base.kb_id } }">{{ base.name }}</router-link></a-space></div>
            <TaskAgentTimeline :key="task.tid" :entries="entries" :model-config="task.config_snapshot" @result="readResult" @preview="previewFile" @subtask="openSubtask" @layout-interaction="following = false" />
            <TaskAgentWorkflowRuns :runs="detail.workflow_runs" :busy="busy" :disabled="syncError || Boolean(pendingRequest)" @feedback="submit('workflow_feedback', { task_id: task.tid, action_id: id(), ...$event })" />
            <TextOutput v-if="active && detail.live?.text" :text="detail.live.text" :show-copy="false" />
            <div v-if="showThinking" class="task-thinking-indicator" role="status" aria-live="polite"><span>{{ t(starting ? 'workspace.taskAgentSpace.starting' : 'workspace.taskAgentSpace.thinking') }}</span></div>
            <p v-if="task.status === 'PAUSED'" class="state-note">{{ t('workspace.taskAgentSpace.paused_description') }}</p>
            <a-alert v-if="!detail.model_rejection_only && ((state.unconfirmedCount > 0 && ['COMPLETED', 'FAILED', 'INTERRUPTED'].includes(task.status)) || detail.mcp_runs?.some(run => run?.status === 'UNKNOWN' || run?.dispatch_uncertain))" class="unconfirmed" type="warning" show-icon :message="t('workspace.taskAgentSpace.unconfirmed_work')" />
            <div v-if="question || task.status === 'PAUSED' || workflowWaiting || parkedMcpWaiting" class="task-controls"><span>{{ t(parkedMcpWaiting ? 'workspace.taskAgentSpace.mcp_unknown_wait_hint' : workflowWaiting ? 'workspace.taskAgentSpace.workflow_answer_above' : question?.kind === 'approval' ? 'workspace.taskAgentSpace.approval_above' : question ? 'workspace.taskAgentSpace.answer_above' : 'workspace.taskAgentSpace.continue_hint') }}</span><a-space v-if="task.status === 'PAUSED'"><IconButton size="small" type="primary" :disabled="starting || busy || syncError || Boolean(pendingRequest)" @click="takeAction({ kind: 'resume' })" :text="t('workspace.taskAgentSpace.resume')"><template #icon><PlayOne /></template></IconButton></a-space></div>
            <TaskAgentInteraction v-if="question" :question="question" :busy="busy" :disabled="syncError || Boolean(pendingRequest)" @answer="takeAction" @approve="approve" />
          </div>
          <a-skeleton v-else-if="loading" active :paragraph="{ rows: 5 }" />
          <a-empty v-else-if="notFound" :description="t('workspace.taskAgentSpace.not_found')" />
        </a-spin>
      </div>
      <footer v-if="task" class="follow-up-area">
        <div class="follow-up-inner">
          <div v-if="!following" class="jump-latest-position"><IconButton class="jump-latest" @click="scrollToLatest" size="small" :text="t('workspace.taskAgentSpace.latest')"><template #icon><Down /></template></IconButton></div>
          <div v-if="pendingRequest && !busy" class="request-retry" role="status"><span>{{ t('workspace.taskAgentSpace.request_uncertain') }}</span><IconButton @click="retryRequest" :text="t('workspace.taskAgentSpace.retry_request')"><template #icon><Refresh /></template></IconButton></div>
          <div v-if="(settingsError || pendingSettings) && !settingsSaving" class="request-retry settings-retry" role="status"><span>{{ settingsError || t('workspace.taskAgentSpace.runtime_settings_uncertain') }}</span><IconButton v-if="pendingSettings" @click="retrySettings" :text="t('workspace.taskAgentSpace.runtime_settings_retry')"><template #icon><Refresh /></template></IconButton></div>
          <TaskAgentModelError v-if="settingsModelFailure" :failure="settingsModelFailure" :model-config="{ selected_model: pendingSettings?.model || runtimeModel }" class="settings-model-error" />
          <div class="follow-up-input" :class="{ 'with-interaction': Boolean(question) }">
            <a-textarea v-if="!question" v-model:value="reply" :aria-label="t('workspace.taskAgentSpace.follow_up_placeholder')" :placeholder="t('workspace.taskAgentSpace.follow_up_placeholder')" :auto-size="{ minRows: 2, maxRows: 8 }" :disabled="active || busy || Boolean(pendingRequest) || workflowWaiting || parkedMcpWaiting || task.status === 'PAUSED'" @keydown.ctrl.enter.prevent="sendMessage" />
            <div class="composer-toolbar">
              <TaskAgentPermissions :model-value="runtimeSettings.permission_mode" :disabled="starting || busy || settingsSaving || Boolean(pendingRequest) || Boolean(pendingSettings) || Boolean(runtimeSettings.pending_change_id)" @update:model-value="changePermission" />
              <div class="composer-right-actions">
                <ModelPicker v-model:model="runtimeModel" v-model:model-provider="runtimeProvider" v-model:preference="runtimePreference" v-model:reasoning-effort="runtimeEffort" :options="modelOptions" :save-selection="changeModel" :loading="settingsSaving" :disabled="starting || busy || settingsSaving || Boolean(pendingRequest) || Boolean(pendingSettings) || Boolean(runtimeSettings.pending_change_id)" />
                <TaskAgentContextUsage :task-id="task.tid" :token-usage="detail.token_usage" :context-window="runtimeSettings.context_length" :disabled="active || busy || settingsSaving || Boolean(pendingRequest) || Boolean(pendingSettings) || Boolean(runtimeSettings.pending_change_id) || Boolean(question) || workflowWaiting || parkedMcpWaiting || task.status === 'PAUSED'" @refresh="loadTask(true)" />
                <a-popconfirm v-if="parkedMcpWaiting" :title="t('workspace.taskAgentSpace.mcp_stop_waiting_confirm')" @confirm="takeAction({ kind: 'cancel' })"><IconButton type="primary" danger size="small" class="composer-stop-btn" :loading="busy" :disabled="starting || busy || syncError || Boolean(pendingRequest)" :aria-label="t('workspace.taskAgentSpace.mcp_stop_waiting')" :text="t('workspace.taskAgentSpace.mcp_stop_waiting')"><template #icon><HandleSquare /></template></IconButton></a-popconfirm>
                <a-popconfirm v-else-if="active || question" :title="t('workspace.taskAgentSpace.stop_confirm')" @confirm="takeAction({ kind: 'cancel' })"><IconButton type="primary" danger shape="circle" class="composer-stop-btn" :loading="busy" :disabled="starting || busy || syncError || Boolean(pendingRequest)" :aria-label="t('workspace.taskAgentSpace.stop')" :text="t('workspace.taskAgentSpace.stop')"><template #icon><HandleSquare /></template></IconButton></a-popconfirm>
                <IconButton v-else type="primary" shape="circle" :loading="busy" :disabled="!canSend" :aria-label="t('workspace.taskAgentSpace.send_message')" @click="sendMessage" :text="t('workspace.taskAgentSpace.send_message')"><template #icon><Send /></template></IconButton>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
    <div v-if="task && showWorkspace && !narrow" class="workspace-resizer" role="separator" tabindex="0" aria-orientation="vertical" :aria-label="t('workspace.taskAgentSpace.resize_workspace')" :aria-valuenow="Math.round(leftWidth)" :aria-valuemin="20" :aria-valuemax="80" @pointerdown="startResize" @pointermove="resize" @pointerup="endResize" @pointercancel="endResize" @lostpointercapture="endResize" @keydown="resizeKey" />
    <TaskAgentWorkspace v-if="task" :key="task.tid" ref="workspace" :visible="showWorkspace" :style="{ flexBasis: narrow ? '100%' : (100 - leftWidth) + '%' }" :task-id="task.tid" :project="task.config_snapshot?.project" :todos="detail.todos" :entries="detail.timeline" :revision="state.projectionWatermark" :profile="task.config_snapshot?.agent_profile" :workflows="task.config_snapshot?.workflow_tools" :skills="task.config_snapshot?.skills" :mcp-tools="task.config_snapshot?.mcp_tools" :mcp-runs="detail.mcp_runs" @close="showWorkspace = false" />
  </main>
</template>
<style scoped>
.task-knowledge-mounts { display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0; font-size: 12px; }
.task-detail-page { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "Noto Sans SC", sans-serif; position: relative; display: flex; height: 100%; min-height: 0; overflow: hidden; background: var(--component-background); }
.task-conversation { position: relative; display: flex; min-width: 0; min-height: 0; flex: 1 1 auto; flex-direction: column; overflow: hidden; }
.detail-breadcrumb { flex-shrink: 0; display: flex; align-items: center; gap: 7px; padding: 12px 24px 0; font-size: 11px; color: var(--site-secondary-text-color); }.detail-breadcrumb a { color: inherit; }.detail-breadcrumb a:hover { color: var(--color-primary); }
.detail-header { flex-shrink: 0; display: flex; min-height: 48px; padding: 6px 16px 10px; align-items: center; gap: 8px; border-bottom: var(--light-border); }
.detail-heading { min-width: 0; flex: 1; }.detail-heading h1 { margin: 0; overflow: hidden; font-size: 15px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.detail-status { flex-shrink: 0; padding: 3px 8px; border-radius: 5px; font-size: 11px; white-space: nowrap; color: var(--site-secondary-text-color); background: var(--gray-background); }
.detail-status.status-completed { color: #3c7c40; background: #edf7ed; }.detail-status.status-processing { color: #167d91; background: #e9f7fa; }.detail-status.status-attention { color: #9a6700; background: #fff5dc; }.detail-status.status-failed { color: #b4453c; background: #fff0ed; }
:deep(.workspace-toggle) { position: relative; display: grid; place-items: center; width: 32px; height: 32px; flex-shrink: 0; border: 0; border-radius: 5px; background: transparent; color: var(--site-secondary-text-color); cursor: pointer; }:deep(.workspace-toggle) small { position: absolute; right: -2px; top: -3px; padding: 0 4px; border-radius: 6px; background: var(--color-primary); color: #fff; font-size: 10px; }
.detail-content { flex: 1; min-height: 0; padding: 0 24px 48px; overflow-y: auto; overflow-x: hidden; }
.task-content { display: flex; flex-direction: column; gap: 20px; max-width: 900px; margin: 0 auto; }
.task-overview { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 16px 0; border-bottom: var(--light-border); font-size: 11px; color: var(--site-secondary-text-color); font-variant-numeric: tabular-nums; }
.overview-agent { display: flex; align-items: center; gap: 8px; margin-right: auto; }.overview-agent > span { display: flex; flex-direction: column; gap: 3px; }.overview-agent strong { font-size: 12px; font-weight: 500; color: var(--site-text-color); }.task-overview time, .task-overview button { display: flex; align-items: center; gap: 5px; }.task-overview button { border: 0; background: transparent; color: var(--color-primary); cursor: pointer; }.overview-cycles { white-space: nowrap; }
.sync-notice { flex-shrink: 0; display: flex; gap: 8px; padding: 6px 24px; align-items: center; justify-content: space-between; font-size: 13px; border-bottom: var(--light-border); }.task-thinking-indicator { align-self: flex-start; padding: 4px 2px 0; color: color-mix(in srgb, var(--site-text-color) 42%, transparent); font-size: 14px; font-weight: 700; letter-spacing: 0; }
.task-thinking-indicator span { display: inline-block; background: linear-gradient(110deg, color-mix(in srgb, var(--site-text-color) 42%, transparent) 0%, var(--color-primary, #28c5e5) 45%, #ffffff 50%, var(--color-primary, #28c5e5) 55%, color-mix(in srgb, var(--site-text-color) 42%, transparent) 100%); background-size: 220% 100%; background-clip: text; -webkit-background-clip: text; color: transparent; animation: task-thinking-sweep 1.5s linear infinite; }
@keyframes task-thinking-sweep { from { background-position: 180% 0; } to { background-position: -80% 0; } }
@media (prefers-reduced-motion: reduce) { .task-thinking-indicator span { animation: none; background: none; -webkit-background-clip: border-box; background-clip: border-box; color: var(--site-secondary-text-color); } }.state-note { color: var(--site-secondary-text-color); padding: 12px 0; }.unconfirmed { margin-top: 12px; }
.follow-up-area { flex-shrink: 0; padding: 12px 24px 20px; background: var(--component-background); }.follow-up-inner { position: relative; width: 100%; max-width: 900px; margin: 0 auto; }.task-controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; margin-bottom: 8px; }.task-controls > span { color: var(--site-secondary-text-color); font-size: 12px; }
.follow-up-input { padding: 10px 14px; border: var(--border-color); border-radius: 12px; background: var(--gray-background); }.follow-up-input:focus-within { border-color: var(--color-primary); }.follow-up-input :deep(textarea) { border: 0; box-shadow: none; background: transparent; resize: none; line-height: 1.7; }
.follow-up-input.with-interaction .composer-toolbar { padding-top: 0; }.composer-toolbar { display: flex; align-items: center; gap: 10px; padding-top: 8px; }.composer-right-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; min-width: 0; max-width: 68%; }.composer-right-actions :deep(.model-picker) { min-width: 0; }:deep(.composer-stop-btn) { flex-shrink: 0; }.settings-model-error { margin-bottom: 10px; }
.request-retry { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; font-size: 13px; }.jump-latest-position { position: absolute; bottom: calc(100% + 12px); left: 50%; transform: translateX(-50%); z-index: 2; } :deep(.jump-latest) { white-space: nowrap; display: flex; align-items: center; gap: 6px; padding: 8px 12px; border: var(--border-color); border-radius: 18px; background: var(--component-background); color: var(--site-text-color); cursor: pointer; box-shadow: 0 2px 8px #0000000d; }
.workspace-resizer { position: relative; width: 6px; flex: 0 0 6px; margin: 0 -3px; z-index: 5; cursor: col-resize; touch-action: none; }.workspace-resizer::after { content: ''; position: absolute; top: calc(50% - 20px); left: 1px; width: 4px; height: 40px; border-radius: 2px; background: color-mix(in srgb, var(--site-text-color) 16%, transparent); }.workspace-resizer:hover::after, .workspace-resizer:focus-visible::after { background: var(--color-primary); }.is-resizing { cursor: col-resize; user-select: none; }
button:focus-visible, .workspace-resizer:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.theme-dark .detail-status { background: #283332; color: #b9d2cc; }
@media (max-width: 1100px) { .detail-content, .follow-up-area { padding-inline: 18px; }.overview-cycles { display: none; } }
@media (max-width: 900px) { .detail-content, .follow-up-area { padding-inline: 16px; }.detail-header { padding-inline: 10px; } }
</style>
