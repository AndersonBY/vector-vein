<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { v4 as uuidv4 } from 'uuid'
import TaskAgentPermissions from '@/views/Workspace/TaskAgent/TaskAgentPermissions.vue'
import TaskAgentProjectEditor from '@/views/Workspace/TaskAgent/TaskAgentProjectEditor.vue'
import TaskAgentProjectPicker from '@/views/Workspace/TaskAgent/TaskAgentProjectPicker.vue'
import TaskAgentWorkspace from '@/views/Workspace/TaskAgent/TaskAgentWorkspace.vue'
import ModelPicker from '@/components/ModelPicker.vue'
import AgentPicker from '@/components/taskAgent/AgentPicker.vue'
import TaskAgentModelError from '@/views/Workspace/TaskAgent/TaskAgentModelError.vue'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import AttachmentsList from '@/components/workspace/AttachmentsList.vue'
import { DoubleRight, Link, Send, MenuUnfoldOne, Edit, Search, Tool, Close, Delete, Down, Refresh, Undo } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { formatIntegrationError } from '@/utils/taskAgentErrors'
import { getChatModelOptions } from '@/utils/common'
import { validModelPair } from '@/utils/modelPreferences'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import { useUserSettingsStore } from '@/stores/userSettings'
import { formatTaskTime, taskStatusClass } from '@/utils/taskAgentPresentation'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const routeProjectId = computed(() => String(route.params.projectId || ''))
const selectedProjectId = ref('')
const projectId = computed(() => routeProjectId.value || selectedProjectId.value)
const projectContext = inject('taskAgentProjectContext', null)
const projectDeletion = inject('taskAgentProjectDeletion', ref(null))
const workbenchDraft = inject('taskAgentWorkbenchDraft', ref(null))
watch(projectId, value => { if (projectContext) projectContext.value = value }, { immediate: true })
const showWorkspace = ref(true)
const layout = ref(null), leftWidth = ref(45), resizing = ref(false), narrow = ref(false)
let mediaQuery = null
let resizeObserver = null
const panelWidth = value => {
  const width = layout.value?.getBoundingClientRect?.().width || 1000
  const minimum = Math.max(20, Math.min(40, 320 / width * 100))
  const maximum = Math.min(80, Math.max(60, 100 - 320 / width * 100))
  leftWidth.value = Math.min(maximum, Math.max(minimum, value))
}
const endResize = () => { resizing.value = false; try { localStorage.setItem('task-agent-project-left-width', String(leftWidth.value)) } catch { /* Storage is optional. */ } }
const startResize = event => { if (event.button !== 0) return; event.preventDefault(); resizing.value = true; event.currentTarget.setPointerCapture?.(event.pointerId) }
const resize = event => { if (!resizing.value) return; const bounds = layout.value.getBoundingClientRect(); panelWidth((event.clientX - bounds.left) / bounds.width * 100) }
const resizeKey = event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  panelWidth(event.key === 'Home' ? 20 : event.key === 'End' ? 80 : leftWidth.value + (event.key === 'ArrowLeft' ? -2 : 2))
  endResize()
}
const updateNarrow = () => { narrow.value = Boolean(mediaQuery?.matches); if (narrow.value) resizing.value = false }
const project = ref(null)
const projectError = ref('')
const projectEditorOpen = ref(false)
let projectRequest = 0
const projectReady = computed(() => !projectId.value || (project.value?.project_id === projectId.value && !project.value.folders?.some(folder => !folder.available)))
const loadProject = async () => {
  const request = ++projectRequest
  project.value = null; projectError.value = ''
  if (!projectId.value) return
  try {
    const response = await taskAgentAPI('project', { project_id: projectId.value })
    if (!alive || request !== projectRequest) return
    if (response.status !== 200) throw new Error()
    project.value = response.data
  } catch { if (alive && request === projectRequest) projectError.value = 'project_load_failed' }
}
const agents = ref([])
const agentId = ref(String(route.query.agent_id || 'general'))
const modelCatalog = useModelCatalogStore()
const settings = useUserSettingsStore()
const goal = ref('')
const modelFailure = ref(null)
const attachments = ref([])
const tasks = ref([])
const taskSearch = ref(''), hasMoreTasks = ref(false)
const searching = computed(() => Boolean(routeProjectId.value && taskSearch.value.trim()))
const loadingActivity = ref(false)
const activityLoaded = ref(false)
const syncError = ref(false)
const sending = ref(false)
const model = ref('')
const modelProvider = ref('')
const preference = ref('default')
const reasoningEffort = ref('default')
const permissionMode = ref('auto')
const mcpTools = ref([])
const mcpToolsLoaded = ref(false)
const mcpToolsFailed = ref(false)
const mcpToolsLoading = ref(false)
const mcpOverride = ref(null)
const mcpPopoverOpen = ref(false)
const mcpSearch = ref('')
const creationIntegrationError = ref('')
let mcpToolsRequest = 0
let suppressAgentWatch = false
let suppressInputRotation = false
const loadMcpTools = async () => {
  const req = ++mcpToolsRequest
  mcpToolsLoading.value = true
  try {
    const res = await taskAgentAPI('mcp_tools')
    if (!alive || req !== mcpToolsRequest) return
    if (res?.status === 200 && Array.isArray(res.data?.tools)) {
      mcpTools.value = res.data.tools
      mcpToolsLoaded.value = true
      mcpToolsFailed.value = false
    } else {
      mcpToolsFailed.value = true
    }
  } catch {
    if (alive && req === mcpToolsRequest) mcpToolsFailed.value = true
  } finally {
    if (alive && req === mcpToolsRequest) mcpToolsLoading.value = false
  }
}
const currentAgent = computed(() => agents.value.find(item => item.agent_id === agentId.value) || null)
const agentDefaultMcpIds = computed(() => Array.isArray(currentAgent.value?.mcp_tool_ids) ? currentAgent.value.mcp_tool_ids : [])
const effectiveMcpToolIds = computed(() => mcpOverride.value !== null ? mcpOverride.value : agentDefaultMcpIds.value)
const unavailableMcpIds = computed(() => {
  if (!mcpToolsLoaded.value || mcpToolsFailed.value) return []
  return effectiveMcpToolIds.value.filter(id => !mcpTools.value.some(tool => tool.namespaced_name === id))
})
const filteredMcpGroups = computed(() => {
  const q = mcpSearch.value.trim().toLowerCase()
  const nameCounts = new Map()
  const serverIdsByName = new Map()
  for (const item of mcpTools.value) {
    const sId = item.server_id || 'mcp'
    const sName = item.server_name || sId
    if (!serverIdsByName.has(sName)) serverIdsByName.set(sName, new Set())
    serverIdsByName.get(sName).add(sId)
  }
  for (const [sName, idSet] of serverIdsByName.entries()) {
    nameCounts.set(sName, idSet.size)
  }
  const groups = new Map()
  for (const item of mcpTools.value) {
    const id = item.namespaced_name
    const serverKey = item.server_id || item.server_name || 'mcp'
    const baseName = item.server_name || serverKey
    const serverLabel = (nameCounts.get(baseName) || 0) > 1 && item.server_id ? `${baseName} (${item.server_id})` : baseName
    const toolLabel = item.title || item.name || id
    const text = `${serverLabel} ${serverKey} ${toolLabel} ${item.name || ''} ${item.description || ''}`.toLowerCase()
    if (q && !text.includes(q)) continue
    if (!groups.has(serverKey)) groups.set(serverKey, { serverId: serverKey, serverLabel, tools: [] })
    groups.get(serverKey).tools.push({ ...item, id, serverLabel, toolLabel })
  }
  return [...groups.values()]
})
const toggleMcpTool = id => {
  if (sending.value) return
  const current = new Set(effectiveMcpToolIds.value)
  if (current.has(id)) current.delete(id)
  else {
    if (current.size >= 64) {
      message.warning(t('workspace.taskAgentSpace.profile_mcp_limit_exceeded'))
      return
    }
    current.add(id)
  }
  mcpOverride.value = [...current]
}
const clearMcpTools = () => { if (!sending.value) mcpOverride.value = [] }
const resetMcpOverride = () => { if (!sending.value) mcpOverride.value = null }
const removeUnavailableWorkbenchMcp = () => {
  if (sending.value) return
  const bad = new Set(unavailableMcpIds.value)
  mcpOverride.value = effectiveMcpToolIds.value.filter(id => !bad.has(id))
}
const navigateToManageMcp = () => {
  if (sending.value) return
  if (workbenchDraft) {
    workbenchDraft.value = {
      originRouteProjectId: routeProjectId.value,
      projectId: projectId.value,
      selectedProjectId: selectedProjectId.value,
      agentId: agentId.value,
      goal: goal.value,
      attachments: JSON.parse(JSON.stringify(attachments.value || [])),
      modelProvider: modelProvider.value,
      model: model.value,
      preference: preference.value,
      reasoningEffort: reasoningEffort.value,
      permissionMode: permissionMode.value,
      mcpOverride: mcpOverride.value !== null ? [...mcpOverride.value] : null,
      inputId: inputId.value,
    }
  }
  mcpPopoverOpen.value = false
  router.push({ name: 'taskAgentMCP' })
}
watch(agentId, () => {
  if (suppressAgentWatch) return
  mcpOverride.value = null
  creationIntegrationError.value = ''
  applyAgentDefaults()
}, { flush: 'sync' })
const inputId = ref(uuidv4().replaceAll('-', ''))
watch([goal, attachments, modelProvider, model, reasoningEffort, agentId, permissionMode, mcpOverride], () => {
  if (!sending.value && !suppressInputRotation) inputId.value = uuidv4().replaceAll('-', '')
}, { deep: true, flush: 'sync' })
const modelOptions = computed(() => getChatModelOptions())
const applyAgentDefaults = () => {
  const agent = agents.value.find(item => item.agent_id === agentId.value)
  permissionMode.value = agent?.permission_mode || 'auto'
  const preset = agent?.model_provider && agent?.model ? agent : settings.setting.data?.model_preferences?.default
  if ((agent?.model_provider && agent?.model) || validModelPair(modelOptions.value, preset?.model_provider, preset?.model)) {
    modelProvider.value = preset.model_provider
    model.value = preset.model
    preference.value = agent?.model ? 'custom' : 'default'
    reasoningEffort.value = preset.reasoning_effort || 'default'
  } else {
    const firstProvider = modelOptions.value[0]
    modelProvider.value = firstProvider?.value || ''
    model.value = firstProvider?.children?.[0]?.value || ''
    preference.value = 'custom'
    reasoningEffort.value = 'default'
  }
}
const submitDisabled = computed(() => (
  sending.value || !projectReady.value || !goal.value.trim() || !validModelPair(modelOptions.value, modelProvider.value, model.value) || unavailableMcpIds.value.length > 0 || (mcpToolsFailed.value && effectiveMcpToolIds.value.length > 0)
))
let requestGeneration = 0
let recentTimer = null
let searchTimer = null
let alive = true

const loadRecent = async (append = false) => {
  if (append && loadingActivity.value) return
  if (recentTimer !== null) window.clearTimeout(recentTimer)
  if (searchTimer !== null) window.clearTimeout(searchTimer)
  const generation = ++requestGeneration
  const limit = searching.value ? 20 : 6
  loadingActivity.value = true
  try {
    const response = await taskAgentAPI('list', { limit, summary: true, sort_by: 'updated_at', sort_order: 'desc', ...(append ? { offset: tasks.value.length } : {}), ...(projectId.value ? { project_id: projectId.value } : {}), ...(searching.value ? { search: taskSearch.value.trim() } : {}) })
    if (generation !== requestGeneration) return
    if (response.status !== 200 || !Array.isArray(response.data?.tasks)) throw new Error()
    if (response.status === 200) {
      tasks.value = append ? [...new Map([...tasks.value, ...response.data.tasks].map(task => [task.tid, task])).values()] : response.data.tasks
      hasMoreTasks.value = searching.value && response.data.tasks.length === limit
      syncError.value = response.data.sync_error
    }
  } catch { if (generation === requestGeneration) syncError.value = true }
  finally {
    if (generation === requestGeneration && alive) {
      loadingActivity.value = false
      activityLoaded.value = true
      if (syncError.value || !searching.value) recentTimer = window.setTimeout(loadRecent, 5000)
    }
  }
}

const refreshRecentOnFocus = () => {
  if (alive && !searching.value && !loadingActivity.value && globalThis.document?.visibilityState !== 'hidden') loadRecent()
}

const submitTask = async () => {
  if (submitDisabled.value) return
  const submittedProject = projectId.value
  mcpPopoverOpen.value = false
  sending.value = true
  modelFailure.value = null
  creationIntegrationError.value = ''
  try {
    const response = await taskAgentAPI('create', {
      input_id: inputId.value,
      turn_input_id: `turn_${uuidv4().replaceAll('-', '')}`,
      goal: goal.value.trim(),
      ...(submittedProject ? { project_id: submittedProject } : {}),
      agent_id: agentId.value,
      attachments: attachments.value,
      model_provider: modelProvider.value,
      model: model.value,
      reasoning_effort: reasoningEffort.value,
      permission_mode: permissionMode.value,
      ...(mcpOverride.value !== null ? { mcp_tool_ids: [...mcpOverride.value] } : {}),
    })
    if (!alive || projectId.value !== submittedProject) return
    if (response.status !== 200) {
      if (response.data?.project_error) { projectError.value = 'project_error_' + response.data.project_error; return }
      if (response.data?.integration_error) {
        creationIntegrationError.value = formatIntegrationError(response, t, 'workspace.taskAgentSpace.create_failed')
        await loadMcpTools()
        return
      }
      modelFailure.value = response.data?.model_failure || null
      if (!modelFailure.value) message.error(response.status === 409 ? response.msg : t('workspace.taskAgentSpace.create_failed'))
      await loadRecent()
      return
    }
    if (workbenchDraft) workbenchDraft.value = null
    goal.value = ''
    attachments.value = []
    mcpOverride.value = null
    inputId.value = uuidv4().replaceAll('-', '')
    await router.push({ name: 'taskAgentDetail', params: { taskId: response.data.task.tid } })
  } catch {
    message.error(t('workspace.taskAgentSpace.create_failed'))
  } finally {
    if (projectId.value === submittedProject) sending.value = false
  }
}

const restoreComposerDraft = () => {
  const savedDraft = workbenchDraft?.value
  const originRoute = savedDraft?.originRouteProjectId ?? ''
  if (!savedDraft || originRoute !== routeProjectId.value || (route.query.agent_id && route.query.agent_id !== savedDraft.agentId)) return false
  suppressAgentWatch = true
  suppressInputRotation = true
  try {
    selectedProjectId.value = savedDraft.selectedProjectId || ''
    agentId.value = savedDraft.agentId || 'general'
    goal.value = savedDraft.goal || ''
    attachments.value = Array.isArray(savedDraft.attachments) ? savedDraft.attachments : []
    modelProvider.value = savedDraft.modelProvider || ''
    model.value = savedDraft.model || ''
    preference.value = savedDraft.preference || 'default'
    reasoningEffort.value = savedDraft.reasoningEffort || 'default'
    permissionMode.value = savedDraft.permissionMode || 'auto'
    mcpOverride.value = Array.isArray(savedDraft.mcpOverride) ? [...savedDraft.mcpOverride] : null
    if (savedDraft.inputId) inputId.value = savedDraft.inputId
  } finally {
    suppressAgentWatch = false
    suppressInputRotation = false
  }
  workbenchDraft.value = null
  return true
}
onMounted(async () => {
  window.addEventListener?.('focus', refreshRecentOnFocus)
  globalThis.document?.addEventListener('visibilitychange', refreshRecentOnFocus)
  const restoredEarly = restoreComposerDraft()
  mediaQuery = globalThis.window?.matchMedia?.('(max-width: 1000px)')
  updateNarrow(); if (narrow.value) showWorkspace.value = false
  mediaQuery?.addEventListener?.('change', updateNarrow)
  try { const saved = Number(localStorage.getItem('task-agent-project-left-width')); if (saved >= 20 && saved <= 80) panelWidth(saved) } catch { /* Storage is optional. */ }
  if (globalThis.ResizeObserver && layout.value) {
    resizeObserver = new ResizeObserver(() => { if (!narrow.value) panelWidth(leftWidth.value) })
    resizeObserver.observe(layout.value)
  }
  loadProject(); loadRecent(); loadMcpTools()
  await modelCatalog.ensureLoaded(true)
  try {
    const response = await taskAgentAPI('profiles')
    if (response.status === 200 && response.data.agents) {
      agents.value = response.data.agents
      if (!restoredEarly) {
        permissionMode.value = agents.value.find(agent => agent.agent_id === agentId.value)?.permission_mode || 'auto'
      }
    }
  } catch { message.error(t('workspace.taskAgentSpace.load_failed')) }
  if (!alive) return
  if (!restoredEarly) {
    applyAgentDefaults()
  }
})
watch(taskSearch, () => {
  requestGeneration++; tasks.value = []; hasMoreTasks.value = false; loadingActivity.value = true; activityLoaded.value = false
  if (recentTimer !== null) window.clearTimeout(recentTimer)
  if (searchTimer !== null) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => loadRecent(), 250)
})
watch(projectId, () => { const hadSearch = Boolean(taskSearch.value); taskSearch.value = ''; requestGeneration++; sending.value = false; modelFailure.value = null; tasks.value = []; activityLoaded.value = false; hasMoreTasks.value = false; if (!suppressInputRotation) inputId.value = uuidv4().replaceAll('-', ''); loadProject(); if (!hadSearch) loadRecent() }, { flush: 'sync' })
watch(projectDeletion, deleted => {
  if (!deleted) return
  if (selectedProjectId.value === deleted.project_id) selectedProjectId.value = ''
  else loadRecent()
})
watch(routeProjectId, () => { goal.value = ''; attachments.value = []; selectedProjectId.value = ''; resizing.value = false; updateNarrow(); showWorkspace.value = !narrow.value })
onBeforeUnmount(() => { alive = false; requestGeneration++; projectRequest++; mcpToolsRequest++; if (projectContext) projectContext.value = ''; if (recentTimer !== null) window.clearTimeout(recentTimer); if (searchTimer !== null) window.clearTimeout(searchTimer); window.removeEventListener?.('focus', refreshRecentOnFocus); globalThis.document?.removeEventListener('visibilitychange', refreshRecentOnFocus); mediaQuery?.removeEventListener?.('change', updateNarrow); resizeObserver?.disconnect() })
</script>

<template>
  <div ref="layout" class="workbench-layout" :style="{ '--project-left-width': leftWidth + '%' }" :class="{ 'with-project-workspace': routeProjectId, 'workspace-open': routeProjectId && project && showWorkspace, 'project-resizing': resizing }">
  <main class="task-workbench" :class="{ 'project-workbench': routeProjectId }">
    <header v-if="routeProjectId" class="project-workbench-header"><router-link class="project-back" :to="{ name: 'taskAgentWorkbench' }">{{ t('workspace.taskAgentSpace.workbench') }}</router-link><IconButton type="text" :aria-label="t('workspace.taskAgentSpace.toggle_workspace')" :aria-pressed="showWorkspace" @click="showWorkspace = !showWorkspace" :text="t('workspace.taskAgentSpace.toggle_workspace')"><template #icon><MenuUnfoldOne /></template></IconButton></header>
    <section class="workbench-hero">
      <h1>{{ routeProjectId ? (project?.name || t('workspace.taskAgentSpace.projects')) : t('workspace.taskAgentSpace.start_title') }}</h1>
      <p v-if="!routeProjectId">{{ t('workspace.taskAgentSpace.start_description') }}</p>

      <div v-if="project && routeProjectId" class="project-context"><div><p v-for="(folder, index) in project.folders" :key="folder.id" :class="{ unavailable: !folder.available }"><strong v-if="index === 0">{{ t('workspace.taskAgentSpace.primary_folder') }}</strong><span :title="folder.path">{{ folder.path }}</span></p></div><IconButton type="text" size="small" :aria-label="t('workspace.taskAgentSpace.edit_project')" @click="projectEditorOpen = true" :text="t('workspace.taskAgentSpace.edit_project')"><template #icon><Edit /></template></IconButton></div>
      <a-alert v-if="projectError || (project && !projectReady)" class="creation-error" type="warning" :message="t('workspace.taskAgentSpace.' + (projectError || 'project_error_folder_unavailable'))"><template #action><IconButton @click="loadProject" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
      <a-alert v-if="creationIntegrationError || unavailableMcpIds.length || (mcpToolsFailed && effectiveMcpToolIds.length)" class="creation-error" type="warning" show-icon :message="creationIntegrationError || (mcpToolsFailed ? t('workspace.taskAgentSpace.workbench_mcp_load_failed') : t('workspace.taskAgentSpace.workbench_mcp_unavailable_warning', { count: unavailableMcpIds.length }))"><template #action><a-space size="small"><IconButton v-if="unavailableMcpIds.length" size="small" :disabled="sending" @click="removeUnavailableWorkbenchMcp" :text="t('workspace.taskAgentSpace.profile_remove_unavailable')"><template #icon><Delete /></template></IconButton><IconButton size="small" :loading="mcpToolsLoading" :disabled="sending" @click="loadMcpTools" :text="t('workspace.taskAgentSpace.workbench_mcp_refresh')"><template #icon><Refresh /></template></IconButton><IconButton size="small" :disabled="sending" @click="navigateToManageMcp" :text="t('workspace.taskAgentSpace.profile_manage_mcp')"><template #icon><Tool /></template></IconButton></a-space></template></a-alert>
      <TaskAgentModelError v-if="modelFailure" :failure="modelFailure" :model-config="{ selected_model: model }" class="creation-error" />
      <div class="composer-shell">
        <div class="composer-contexts">
          <TaskAgentProjectPicker v-if="!routeProjectId" v-model="selectedProjectId" :project="project" :disabled="sending" />
          <div class="agent-context-row">
            <AgentPicker v-model="agentId" :agents="agents" compact :disabled="sending" />
          </div>
        </div>
        <div v-if="!model" class="model-required">
          <router-link :to="{ name: 'settings' }">{{ t('workspace.taskAgentSpace.configure_model') }}</router-link>
        </div>
        <div class="input-wrapper">
          <AttachmentsList v-if="attachments.length" v-model="attachments" class="composer-attachments" />
          <a-textarea
            v-model:value="goal"
            class="task-input"
            :placeholder="t('workspace.taskAgentSpace.goal_placeholder')"
            :auto-size="{ minRows: 5, maxRows: 12 }"
            :disabled="sending"
            @keyup.ctrl.enter="submitTask" />
          <div class="composer-actions">
            <a-tooltip :title="t('workspace.taskAgentSpace.attachments')">
              <UploaderFieldUse
                v-model="attachments"
                support-file-types="*.*"
                :accept-paste="true"
                :multiple="true"
                :show-upload-list="false"
                :single-button="true"
                :single-button-props="{ type: 'text', disabled: sending }">
                <template #icon><Link /></template>
              </UploaderFieldUse>
            </a-tooltip>
            <TaskAgentPermissions v-model="permissionMode" class="task-permissions" :disabled="sending" />
            <a-popover v-model:open="mcpPopoverOpen" :trigger="['click']" placement="topLeft" overlay-class-name="workbench-mcp-popover">
              <template #content>
                <div class="mcp-connector-popup" role="region" :aria-label="t('workspace.taskAgentSpace.workbench_mcp_title')">
                  <div class="mcp-popup-header">
                    <strong>{{ t('workspace.taskAgentSpace.workbench_mcp_title') }}</strong>
                    <span class="mcp-popup-mode">{{ t(mcpOverride === null ? 'workspace.taskAgentSpace.workbench_mcp_following_agent' : 'workspace.taskAgentSpace.workbench_mcp_custom_override', { count: effectiveMcpToolIds.length }) }}</span>
                  </div>
                  <div class="mcp-popup-actions">
                    <IconButton v-if="mcpOverride !== null" size="small" :disabled="sending" @click="resetMcpOverride" :text="t('workspace.taskAgentSpace.workbench_mcp_reset_default')"><template #icon><Undo /></template></IconButton>
                    <IconButton v-if="effectiveMcpToolIds.length > 0 || mcpOverride === null" size="small" :disabled="sending" @click="clearMcpTools" :text="t('workspace.taskAgentSpace.workbench_mcp_clear_all')"><template #icon><Close /></template></IconButton>
                    <IconButton v-if="unavailableMcpIds.length" size="small" danger :disabled="sending" @click="removeUnavailableWorkbenchMcp" :text="t('workspace.taskAgentSpace.profile_remove_unavailable')"><template #icon><Delete /></template></IconButton>
                    <IconButton size="small" class="mcp-manage-link" :disabled="sending" @click="navigateToManageMcp" :text="t('workspace.taskAgentSpace.profile_manage_mcp')"><template #icon><Tool /></template></IconButton>
                  </div>
                  <a-alert v-if="mcpToolsFailed" type="warning" show-icon :message="t('workspace.taskAgentSpace.workbench_mcp_load_failed')">
                    <template #action><IconButton size="small" :loading="mcpToolsLoading" :disabled="sending" @click="loadMcpTools" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template>
                  </a-alert>
                  <a-input v-model:value="mcpSearch" size="small" allow-clear :disabled="sending" :placeholder="t('workspace.taskAgentSpace.workbench_mcp_search')" :aria-label="t('workspace.taskAgentSpace.workbench_mcp_search')" class="mcp-popup-search" />
                  <div v-if="unavailableMcpIds.length" class="mcp-unavailable-list">
                    <div v-for="missingId in unavailableMcpIds" :key="missingId" class="mcp-tool-item unavailable">
                      <a-checkbox :checked="true" :disabled="sending" @change="toggleMcpTool(missingId)">
                        <span>{{ t('workspace.taskAgentSpace.profile_missing_mcp_tool', { id: missingId }) }}</span>
                      </a-checkbox>
                    </div>
                  </div>
                  <div v-if="filteredMcpGroups.length" class="mcp-groups-list">
                    <div v-for="group in filteredMcpGroups" :key="group.serverId" class="mcp-server-group" :data-server-id="group.serverId">
                      <div class="mcp-group-title">{{ group.serverLabel }}</div>
                      <label v-for="item in group.tools" :key="item.id" class="mcp-tool-item">
                        <a-checkbox :checked="effectiveMcpToolIds.includes(item.id)" :disabled="sending" @change="toggleMcpTool(item.id)">
                          <span class="mcp-tool-label">{{ item.toolLabel }}</span>
                          <small v-if="item.name && item.name !== item.toolLabel" class="mcp-tool-code">{{ item.name }}</small>
                        </a-checkbox>
                      </label>
                    </div>
                  </div>
                  <p v-else-if="!mcpToolsFailed" class="mcp-popup-empty">{{ t('workspace.taskAgentSpace.workbench_mcp_empty') }}</p>
                </div>
              </template>
              <a-button type="text" size="small" class="workbench-mcp-trigger" :class="{ 'mcp-overridden': mcpOverride !== null, 'mcp-has-unavailable': unavailableMcpIds.length > 0 }" :disabled="sending" :aria-label="t('workspace.taskAgentSpace.workbench_mcp_button')">
                <template #icon><Tool /></template>
                <span>{{ t('workspace.taskAgentSpace.workbench_mcp_button') }}</span>
                <span v-if="effectiveMcpToolIds.length || mcpOverride !== null" class="mcp-trigger-badge">{{ effectiveMcpToolIds.length }}</span>
              </a-button>
            </a-popover>
            <div class="composer-right-actions">
              <ModelPicker
                v-model:model="model"
                v-model:model-provider="modelProvider"
                v-model:preference="preference"
                v-model:reasoning-effort="reasoningEffort"
                class="composer-model-picker"
                :options="modelOptions"
                :disabled="sending" />
              <IconButton
                  type="primary"
                  shape="circle"
                  class="send-task"
                  :loading="sending"
                  :disabled="submitDisabled"
                  :aria-label="t('workspace.taskAgentSpace.send_task')"
                  @click="submitTask" :text="t('workspace.taskAgentSpace.send_task')"><template #icon><Send /></template></IconButton>
            </div>
          </div>
        </div>
        <p v-if="permissionMode === 'auto' && !settings.setting.data?.task_agent_approval?.model" class="reviewer-setup"><router-link :to="{ name: 'settings', query: { section: 'model_preferences' } }">{{ t('workspace.taskAgentSpace.risk_configure') }}</router-link> · {{ t('workspace.taskAgentSpace.risk_model_unset') }}</p>
      </div>
    </section>

    <section class="recent-section" aria-labelledby="recent-task-title">
      <header class="section-header">
        <h2 id="recent-task-title">{{ t(searching ? 'workspace.taskAgentSpace.project_search_results' : 'workspace.taskAgentSpace.recent_activity') }}</h2>
        <router-link :to="{ name: 'taskAgentTasks', query: projectId ? { project_id: projectId } : {} }">{{ t('workspace.taskAgentSpace.view_all_tasks') }}</router-link>
      </header>
      <a-input v-if="routeProjectId" v-model:value="taskSearch" class="project-task-search" allow-clear :maxlength="256" :placeholder="t('workspace.taskAgentSpace.search_project_tasks')" :aria-label="t('workspace.taskAgentSpace.search_project_tasks')"><template #prefix><Search /></template></a-input>
      <div v-if="syncError" class="sync-notice" role="status">
        <span>{{ t('workspace.taskAgentSpace.sync_error') }}</span>
        <IconButton @click="loadRecent()" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
      </div>
      <a-spin :spinning="loadingActivity && !activityLoaded">
        <div v-if="tasks.length" class="recent-list">
          <button
            v-for="task in tasks"
            :key="task.tid"
            type="button"
            class="recent-task"
            @click="router.push({ name: 'taskAgentDetail', params: { taskId: task.tid } })">
            <span class="task-state" :class="taskStatusClass(task.status)" />
            <span class="recent-task-copy">
              <strong>{{ task.title }}</strong>
              <small>{{ formatTaskTime(task.updated_at, locale) }}</small>
            </span>
            <span class="status-label">{{ t(`workspace.taskAgentSpace.status_${task.status}`) }}</span>
            <DoubleRight class="open-task" />
          </button>
        </div>
        <a-empty v-else :description="t(searching ? 'workspace.taskAgentSpace.no_matching_tasks' : 'workspace.taskAgentSpace.no_recent_activity')" />
        <IconButton v-if="searching && hasMoreTasks" class="project-search-more" type="text" :loading="loadingActivity" @click="loadRecent(true)" :text="t('common.load_more')"><template #icon><Down /></template></IconButton>
      </a-spin>
    </section>
    <TaskAgentProjectEditor v-model:open="projectEditorOpen" :project="project" @saved="project = $event" />
  </main>
  <div v-if="routeProjectId && project && showWorkspace && !narrow" class="project-workspace-resizer" role="separator" tabindex="0" aria-orientation="vertical" :aria-label="t('workspace.taskAgentSpace.resize_project_workspace')" :aria-valuenow="Math.round(leftWidth)" :aria-valuemin="20" :aria-valuemax="80" @pointerdown="startResize" @pointermove="resize" @pointerup="endResize" @pointercancel="endResize" @lostpointercapture="endResize" @keydown="resizeKey" />
  <TaskAgentWorkspace v-if="routeProjectId && project" :key="routeProjectId" :project-id="routeProjectId" :project="project" :revision="project.updated_at" :visible="showWorkspace" class="project-workspace" @close="showWorkspace = false" />
  </div>
</template>

<style scoped>
.workbench-layout { min-height: 100%; }
.with-project-workspace { position: relative; display: flex; height: 100%; min-height: 0; overflow: hidden; }
.with-project-workspace > .task-workbench { flex: 1; min-height: 0; height: 100%; overflow-y: auto; padding: 24px; }
.with-project-workspace.workspace-open > .task-workbench { flex: 0 0 var(--project-left-width); width: var(--project-left-width); min-width: 0; margin: 0; }
.with-project-workspace > .project-workspace { flex: 1; }
.project-workspace-resizer { position: relative; flex: 0 0 6px; width: 6px; z-index: 5; cursor: col-resize; touch-action: none; }
.project-workspace-resizer::after { content: ''; position: absolute; top: calc(50% - 20px); left: 1px; width: 4px; height: 40px; border-radius: 2px; background: color-mix(in srgb, var(--site-text-color) 16%, transparent); }
.project-workspace-resizer:hover::after, .project-workspace-resizer:focus-visible::after { background: var(--color-primary); }
.project-workspace-resizer:focus-visible { outline: 2px solid var(--color-primary); outline-offset: -2px; }
.project-resizing { cursor: col-resize; user-select: none; }.project-resizing :deep(iframe) { pointer-events: none; }
.project-task-search { margin: 8px 0 12px; }:deep(.project-search-more) { margin-top: 8px; }
.project-workbench .workbench-hero h1 { margin-bottom: 20px; }
.project-workbench-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 20px; }.project-workbench-header .project-back { margin-bottom: 0; }
@media (max-width: 1000px) { .with-project-workspace.workspace-open > .task-workbench { flex: 1; width: 100%; }.project-workspace { position: absolute; inset: 0; width: 100%; z-index: 20; } }
.project-back { display: inline-block; margin-bottom: 20px; color: var(--site-secondary-text-color); font-size: 13px; }.project-workbench { padding-top: 28px; }.project-workbench .workbench-hero h1, .project-workbench .workbench-hero > p { text-align: left; }.project-workbench .workbench-hero h1 { font-size: 24px; }.project-context { display: flex; gap: 16px; align-items: flex-start; padding: 0 0 24px; }.project-context > div { min-width: 0; flex: 1; }.project-context p { display: flex; align-items: baseline; gap: 8px; margin: 0 0 6px; color: var(--site-secondary-text-color); font-size: 12px; }.project-context strong { flex-shrink: 0; font-size: 11px; font-weight: 500; }.project-context span { overflow-wrap: anywhere; }.project-context .unavailable { color: var(--error-color); }

.reviewer-setup { margin: 6px 16px 12px; font-size: 12px; color: var(--site-secondary-text-color); }
.creation-error { margin-bottom: 20px; }
.task-workbench {
  width: min(960px, 100%);
  min-height: 100%;
  margin: 0 auto;
  padding: 64px 32px 48px;
}
.workbench-hero {
  width: min(800px, 100%);
  margin: 0 auto;
}
.workbench-hero h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1.35;
  text-align: center;
}
.workbench-hero > p {
  margin: 10px 0 28px;
  color: var(--site-secondary-text-color);
  font-size: 14px;
  text-align: center;
}
.composer-contexts {
  display: flex;
  max-width: calc(100% - 24px);
  flex-wrap: wrap;
  margin: 0 0 -1px 14px;
  gap: 8px;
}
.agent-context-row {
  display: flex;
  min-width: 0;
  max-width: 260px;
  min-height: 38px;
  align-items: center;
  gap: 7px;
  border: var(--border-color);
  border-bottom: 0;
  border-radius: 8px 8px 0 0;
  background: var(--component-background);
  font-size: 13px;
}
.agent-context-row :deep(.task-agent-picker-trigger) { height: 38px; border: 0; border-radius: 8px 8px 0 0; box-shadow: none; }
.composer-right-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; min-width: 0; max-width: 60%; }
.composer-model-picker { flex: 0 1 auto; min-width: 0; max-width: 100%; }
:deep(.send-task) { flex-shrink: 0; }
.model-required { margin: 8px 0; text-align: right; font-size: 13px; }
.model-required a { color: var(--color-primary); }
.input-wrapper {
  padding: 14px 16px 10px;
  border: var(--border-color);
  border-radius: 8px;
  background: var(--component-background);
  box-shadow: 0 6px 24px rgb(0 0 0 / 6%);
}
.input-wrapper:focus-within { border-color: var(--color-primary); }
.composer-attachments { margin-bottom: 12px; }
.task-input {
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
  font-size: 15px;
  line-height: 1.6;
  resize: none;
}
.task-input:focus { border: 0; box-shadow: none; }
.composer-actions {
  display: flex;
  margin-top: 8px;
  align-items: center;
  gap: 8px;
}
.task-permissions { margin-right: 0; }
.workbench-mcp-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  height: 28px;
  border-radius: 6px;
  color: var(--site-secondary-text-color);
  font-size: 12px;
}
.workbench-mcp-trigger.mcp-overridden {
  color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 8%, transparent);
}
.workbench-mcp-trigger.mcp-has-unavailable {
  color: #d48806;
}
.mcp-trigger-badge {
  display: inline-block;
  padding: 0 5px;
  border-radius: 8px;
  background: var(--gray-background);
  font-size: 11px;
  line-height: 16px;
  font-variant-numeric: tabular-nums;
}
.mcp-connector-popup {
  width: 320px;
  max-width: 86vw;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mcp-popup-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}
.mcp-popup-mode {
  font-size: 11px;
  color: var(--site-secondary-text-color);
}
.mcp-popup-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.mcp-popup-actions :deep(.ant-btn-link) {
  padding: 0;
  height: auto;
  font-size: 12px;
}
:deep(.mcp-manage-link) {
  margin-left: auto;
  font-size: 12px;
}
.mcp-groups-list {
  max-height: 240px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}
.mcp-server-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.mcp-group-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--site-secondary-text-color);
}
.mcp-tool-item {
  display: flex;
  align-items: center;
  padding: 3px 4px;
  border-radius: 4px;
  font-size: 12px;
}
.mcp-tool-item.unavailable {
  background: color-mix(in srgb, #faad14 12%, transparent);
}
.mcp-tool-label {
  font-weight: 500;
}
.mcp-tool-code {
  margin-left: 6px;
  color: var(--site-secondary-text-color);
  font-size: 11px;
}
.mcp-popup-empty {
  margin: 8px 0;
  font-size: 12px;
  color: var(--site-secondary-text-color);
}

.recent-section { margin-top: 52px; }
.section-header {
  display: flex;
  margin-bottom: 8px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.section-header h2 { margin: 0; font-size: 16px; font-weight: 600; }
.section-header a { color: var(--color-primary); font-size: 13px; }
.sync-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--site-secondary-text-color);
  font-size: 13px;
}
.recent-list { border-top: var(--light-border); }
.recent-task {
  display: flex;
  width: 100%;
  min-height: 62px;
  padding: 10px 6px;
  align-items: center;
  gap: 12px;
  border: 0;
  border-bottom: var(--light-border);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.recent-task:hover { background: var(--more-hover-background); }
.recent-task:focus-visible { outline: 2px solid var(--color-primary); outline-offset: -2px; }
.task-state { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 50%; background: #8c8c8c; }
.status-completed { background: #52c41a; }
.status-processing { background: #28c5e5; }
.status-pending, .status-attention { background: #d48806; }
.status-failed { background: #ff4d4f; }
.status-paused { background: #8c8c8c; }
.recent-task-copy { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }
.recent-task-copy strong,
.recent-task-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-task-copy strong { font-size: 14px; font-weight: 500; }
.recent-task-copy small,
.status-label,
.open-task { color: var(--site-secondary-text-color); font-size: 12px; }
@media (max-width: 820px) {
  .task-workbench { padding: 40px 16px; }
  .workbench-hero h1 { font-size: 24px; }
  .status-label { display: none; }
}
</style>
