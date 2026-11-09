<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { DocDetail, FolderOpen, OpenExternal, Refresh, CheckOne, CircleFourLine, LoadingFour, Plus, Close, OffScreenOne, FullScreenOne, Tool, Robot, ListOne, Down } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { commandStatus, fileSize, isMcpUnknown, toolDisplaySummary, toolResultPresentation, taskFileLink, toolStatusKey } from '@/utils/taskAgentTimeline'
import TextOutput from '@/components/TextOutput.vue'
import VueMarkdown from 'vue-markdown-render'
const props = defineProps({ taskId: { type: String, default: '' }, projectId: { type: String, default: '' }, todos: { type: Array, default: () => [] }, revision: [Number, String], profile: Object, project: Object, workflows: { type: Array, default: () => [] }, skills: { type: Array, default: () => [] }, mcpTools: { type: Array, default: () => [] }, mcpRuns: { type: Array, default: () => [] }, entries: { type: Array, default: () => [] }, visible: { type: Boolean, default: true } })
const emit = defineEmits(['close'])
const { t, te } = useI18n()
const uid = useId()
const tabbar = ref(null)
const files = ref([])
const loading = ref(false)
const failed = ref(false)
const limited = ref(false)
const search = ref('')
const rootId = ref('0')
const projectFolders = computed(() => (props.project?.roots || []).map((path, index) => ({ value: String(index), label: path })))
const fileAPI = (action, payload) => taskAgentAPI(props.projectId ? 'project_' + action : action, { ...(props.projectId ? { project_id: props.projectId } : { task_id: props.taskId }), ...payload })
const active = ref('files')
const expanded = ref(false)
const tabs = ref([{ id: 'files', kind: 'files' }])
const current = computed(() => tabs.value.find(tab => tab.id === active.value) || tabs.value[0])
const tools = computed(() => {
  const rootTools = props.entries.filter(entry => entry.kind === 'tool')
  const matchedCallKeys = new Set(rootTools.map(entry => `${entry.turn_id || ''}::${entry.tool_call_id || ''}`))
  const extraRuns = (props.mcpRuns || []).filter(run => {
    if (!run?.job_id) return false
    const isChild = Boolean(props.taskId && run.session_id && run.session_id !== props.taskId)
    const key = `${run.turn_id || ''}::${run.tool_call_id || ''}`
    return isChild || !matchedCallKeys.has(key)
  }).map(run => {
    const isChild = Boolean(props.taskId && run.session_id && run.session_id !== props.taskId)
    const status = (run.status === 'UNKNOWN' || run.dispatch_uncertain)
      ? 'unknown'
      : run.status === 'FINISHED'
        ? 'success'
        : run.status === 'FAILED'
          ? 'error'
          : run.status === 'CANCELLED'
            ? 'cancelled'
            : run.status === 'DISPATCHING'
              ? 'running'
              : 'pending'
    const matchedTool = (props.mcpTools || []).find(item => item.namespaced_name === run.namespaced_name || (item.server_id === run.server_id && item.name === run.tool_name))
    const serverLabel = run.server_name || matchedTool?.server_name || run.server_id || 'MCP'
    const toolLabel = matchedTool?.title || run.tool_name || run.namespaced_name || ''
    return {
      id: `mcp_job:${run.job_id}`,
      kind: 'tool',
      turn_id: run.turn_id || '',
      session_id: run.session_id || '',
      is_child_session: isChild,
      tool_call_id: run.tool_call_id || '',
      tool_name: run.namespaced_name || run.tool_name || '',
      display_name: `${serverLabel}: ${toolLabel}`,
      status,
      error_code: run.error_code || run.unknown_code || '',
      mcp_run: run,
      arguments: {},
    }
  })
  return [...rootTools, ...extraRuns]
})
const children = computed(() => props.entries.filter(entry => entry.kind === 'sub_agent'))
const completed = computed(() => props.todos.filter(todo => todo.status === 'completed').length)
const directoryGroups = computed(() => {
  const groups = new Map()
  for (const file of files.value.filter(file => file.path.toLowerCase().includes(search.value.trim().toLowerCase()))) {
    const relative = file.relative_path || file.path
    const directory = relative.includes('/') ? relative.slice(0, relative.lastIndexOf('/')) : '.'
    if (!groups.has(directory)) groups.set(directory, [])
    groups.get(directory).push(file)
  }
  return [...groups].sort(([a], [b]) => a.localeCompare(b))
})
const toolFor = tab => tools.value.find(entry => entry.id === tab.entryId) || tab.entry
const childFor = tab => children.value.find(entry => entry.child_session_id === tab.childId) || tab.entry
const currentTool = computed(() => current.value.kind === 'tool' ? toolFor(current.value) : null)
const presentedResult = computed(() => toolResultPresentation(currentTool.value, current.value.text ?? currentTool.value?.result?.preview))
const extraCommandArguments = computed(() => Object.fromEntries(Object.entries(currentTool.value?.arguments || {}).filter(([key]) => key !== 'command')))
const canRenderFile = computed(() => current.value.preview?.kind === 'text' && (current.value.preview.markdown || (/\.html?$/i.test(current.value.path) && !current.value.preview.truncated)))
const htmlPreview = computed(() => '<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'"><meta charset="utf-8">' + (current.value.preview?.text || ''))
const currentChild = computed(() => current.value.kind === 'subtask' ? childFor(current.value) : null)
const fileFor = tab => files.value.find(file => file.path === tab.path) || tab.file || { path: tab.path, name: tab.path?.split('/').pop() }
const readOnlyFile = computed(() => current.value.path?.startsWith('.knowledge/') || current.value.preview?.read_only || fileFor(current.value).read_only)
const displayPath = path => {
  const match = path?.match(/^project-files\/(\d+)\/(.+)$/)
  const root = match && props.project?.roots?.[Number(match[1])]
  return root ? root.replaceAll('\\', '/').replace(/\/$/, '') + '/' + match[2] : path
}
const toolTitle = entry => entry?.display_name || (te('workspace.taskAgentSpace.tool_' + entry?.tool_name) ? t('workspace.taskAgentSpace.tool_' + entry.tool_name) : entry?.tool_name || '')
const tabTitle = tab => tab.kind === 'file' ? fileFor(tab).name : tab.kind === 'tool' ? toolTitle(toolFor(tab)) : tab.kind === 'subtask' ? t('workspace.taskAgentSpace.sub_agent') + ' ' + (children.value.findIndex(child => child.child_session_id === tab.childId) + 1) : t('workspace.taskAgentSpace.' + tab.kind)
const tabIcon = tab => ({ files: FolderOpen, file: DocDetail, tool: Tool, tools: Tool, subtask: Robot, subtasks: Robot, plan: ListOne, agent: Robot, workspace_home: Plus }[tab.kind])
let generation = 0
let filesRequest = 0
let alive = true
const openTab = tab => {
  if (!tabs.value.some(item => item.id === tab.id)) tabs.value.push(tab)
  active.value = tab.id
  return tabs.value.find(item => item.id === tab.id)
}
const focusActive = async () => { await nextTick(); tabbar.value?.querySelectorAll?.('[role="tab"]')[tabs.value.findIndex(tab => tab.id === active.value)]?.focus?.() }
const closeTab = id => {
  if (id === 'files') return
  const index = tabs.value.findIndex(tab => tab.id === id)
  if (index < 0) return
  tabs.value.splice(index, 1)
  if (active.value === id) active.value = tabs.value[Math.min(index, tabs.value.length - 1)].id
  focusActive()
}
const tabKey = (event, id) => {
  const index = tabs.value.findIndex(tab => tab.id === id)
  const offset = { ArrowLeft: -1, ArrowRight: 1 }[event.key]
  if (offset || ['Home', 'End'].includes(event.key)) {
    event.preventDefault()
    active.value = tabs.value[event.key === 'Home' ? 0 : event.key === 'End' ? tabs.value.length - 1 : (index + offset + tabs.value.length) % tabs.value.length].id
    focusActive()
  } else if (event.key === 'Delete') { event.preventDefault(); closeTab(id) }
}
const loadFiles = async () => {
  const request = ++filesRequest
  const scope = generation
  loading.value = true
  try {
    const response = await fileAPI('files', { root_id: rootId.value })
    if (!alive || scope !== generation || request !== filesRequest) return
    if (response.status !== 200) throw new Error()
    files.value = response.data.files
    limited.value = response.data.limited
    failed.value = false
  } catch { if (alive && scope === generation && request === filesRequest) failed.value = true }
  finally { if (alive && scope === generation && request === filesRequest) loading.value = false }
}
const loadPreview = async tab => {
  const scope = generation
  const request = (tab.request || 0) + 1
  tab.request = request; tab.loading = true; tab.error = false
  try {
    const response = await fileAPI('preview_file', { path: tab.path })
    if (!alive || scope !== generation || !tabs.value.includes(tab) || tab.request !== request) return
    if (response.status !== 200) throw new Error()
    tab.preview = response.data
  } catch { if (alive && scope === generation && tabs.value.includes(tab) && tab.request === request) tab.error = true }
  finally { if (alive && scope === generation && tabs.value.includes(tab) && tab.request === request) tab.loading = false }
}
const showPreview = path => {
  const tab = openTab({ id: `file:${path}`, kind: 'file', path, preview: null, view: 'preview', file: files.value.find(file => file.path === path) })
  if (!tab.preview && !tab.loading) loadPreview(tab)
}
const readTool = async (tab, append = false) => {
  const entry = toolFor(tab)
  if (!entry?.result_event_id || tab.loading) return
  const scope = generation
  const eventId = entry.result_event_id
  tab.loading = true; tab.error = false
  if (!append) { tab.bytes = []; tab.nextOffset = 0; tab.text = '' }
  try {
    const response = await taskAgentAPI('tool_result', { task_id: props.taskId, event_id: eventId, offset: tab.nextOffset || 0 })
    if (!alive || scope !== generation || !tabs.value.includes(tab)) return
    if (response.status !== 200) throw new Error()
    tab.bytes.push(Uint8Array.from(atob(response.data.data), char => char.charCodeAt(0)))
    const combined = new Uint8Array(tab.bytes.reduce((sum, part) => sum + part.length, 0))
    let offset = 0
    for (const part of tab.bytes) { combined.set(part, offset); offset += part.length }
    tab.text = new TextDecoder().decode(combined, { stream: response.data.eof !== true && response.data.nextOffset !== null })
    tab.nextOffset = response.data.eof === true ? null : response.data.nextOffset
    tab.loadedEventId = eventId
  } catch { if (alive && scope === generation && tabs.value.includes(tab)) tab.error = true }
  finally { if (alive && scope === generation && tabs.value.includes(tab)) tab.loading = false }
}
const openTool = entry => {
  const tab = openTab({ id: `tool:${entry.id}`, kind: 'tool', entryId: entry.id, entry, text: null, nextOffset: null })
  if (entry.result_event_id && tab.loadedEventId !== entry.result_event_id) readTool(tab)
}
const openSubtask = entry => openTab({ id: `subtask:${entry.child_session_id}`, kind: 'subtask', childId: entry.child_session_id, entry })
const launch = kind => openTab({ id: kind, kind })
const onFileLink = event => {
  const link = event.target.closest?.('a')
  if (!link || link.classList?.contains('snapshot-skill-link')) return
  const href = link.getAttribute('href') || ''
  const path = taskFileLink(href, Boolean(props.project))
  if (!path) return
  event.preventDefault(); event.stopPropagation()
  try { showPreview(decodeURIComponent(path)) } catch { message.error(t('workspace.taskAgentSpace.file_failed')) }
}
const openFile = async reveal => {
  const path = current.value.path
  if (!path || readOnlyFile.value) return
  try {
    const response = await fileAPI('open_file', { path, reveal })
    if (response.status !== 200) throw new Error()
  } catch { message.error(t('workspace.taskAgentSpace.file_failed')) }
}
watch(() => currentTool.value?.result_event_id, eventId => { if (eventId && current.value.loadedEventId !== eventId) readTool(current.value) })
watch([() => props.taskId, () => props.projectId, () => props.projectId ? JSON.stringify(props.project?.roots || []) : ''], () => { generation++; filesRequest++; files.value = []; tabs.value = [{ id: 'files', kind: 'files' }]; active.value = 'files'; expanded.value = false; search.value = ''; rootId.value = '0'; loadFiles() }, { immediate: true })
watch([() => props.revision, () => props.visible], () => { if (props.visible) loadFiles() })
onBeforeUnmount(() => { alive = false; generation++; filesRequest++ })
watch(rootId, () => { files.value = []; search.value = ''; loadFiles() })
defineExpose({ showPreview, openTool, openSubtask, launch })
</script>
<template>
  <aside v-show="visible" class="workspace-panel" :class="{ 'workspace-expanded': expanded }" :aria-label="t('workspace.taskAgentSpace.workspace')" @keydown.esc="expanded = false" @click.capture="onFileLink">
    <header class="workspace-tabbar">
      <div ref="tabbar" class="workspace-tablist" role="tablist" :aria-label="t('workspace.taskAgentSpace.open_tabs')">
        <div v-for="(tab, index) in tabs" :key="tab.id" class="workspace-tab" :class="{ active: active === tab.id }">
          <button :id="`${uid}-tab-${index}`" type="button" role="tab" :aria-selected="active === tab.id" :aria-controls="`${uid}-panel`" :tabindex="active === tab.id ? 0 : -1" :title="displayPath(tab.path) || tabTitle(tab)" @click="active = tab.id" @keydown="tabKey($event, tab.id)"><component :is="tabIcon(tab)" size="16" /><span>{{ tabTitle(tab) }}</span></button>
          <IconButton v-if="tab.id !== 'files'" class="tab-close" :aria-label="t('workspace.taskAgentSpace.close_tab', { title: tabTitle(tab) })" @click="closeTab(tab.id)" size="small" :text="t('workspace.taskAgentSpace.close_tab', { title: tabTitle(tab) })"><template #icon><Close size="12" /></template></IconButton>
        </div>
      </div>
      <IconButton class="workspace-icon-button" :aria-label="t('workspace.taskAgentSpace.' + (projectId ? 'browse_project_files' : 'new_workspace_tab'))" @click="projectId ? active = 'files' : launch('workspace_home')" size="small" :text="t('workspace.taskAgentSpace.' + (projectId ? 'browse_project_files' : 'new_workspace_tab'))"><template #icon><Plus /></template></IconButton>
      <div class="workspace-actions"><IconButton class="workspace-icon-button" :aria-label="t('workspace.taskAgentSpace.expand_workspace')" :aria-pressed="expanded" @click="expanded = !expanded" size="small" :text="t('workspace.taskAgentSpace.expand_workspace')"><template #icon><OffScreenOne v-if="expanded" /><FullScreenOne v-else /></template></IconButton><IconButton class="workspace-icon-button" :aria-label="t('workspace.taskAgentSpace.close_workspace')" @click="expanded = false; emit('close')" size="small" :text="t('workspace.taskAgentSpace.close_workspace')"><template #icon><Close /></template></IconButton></div>
    </header>
    <section :id="`${uid}-panel`" role="tabpanel" :aria-labelledby="`${uid}-tab-${tabs.findIndex(tab => tab.id === active)}`" class="workspace-body">
      <template v-if="current.kind === 'files'">
        <div class="workspace-page">
          <div class="page-heading"><h2>{{ t('workspace.taskAgentSpace.files') }}</h2><IconButton type="text" size="small" :aria-label="t('workspace.taskAgentSpace.refresh_files')" :loading="loading" @click="loadFiles" :text="t('workspace.taskAgentSpace.refresh_files')"><template #icon><Refresh /></template></IconButton></div>
          <p class="page-description">{{ t('workspace.taskAgentSpace.' + (projectId ? 'project_files_description' : 'files_description')) }}</p>
          <a-select v-if="projectFolders.length" v-model:value="rootId" class="project-root-select" :options="projectFolders" :aria-label="t('workspace.taskAgentSpace.project_folders')" />
          <a-input v-model:value="search" allow-clear :placeholder="t('workspace.taskAgentSpace.find_file')" :aria-label="t('workspace.taskAgentSpace.find_file')" />
          <a-alert v-if="failed" type="warning" :message="t('workspace.taskAgentSpace.file_failed')"><template #action><IconButton @click="loadFiles" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
          <div class="file-groups"><details v-for="[directory, items] in directoryGroups" :key="directory" open><summary>{{ directory }} <small>{{ items.length }}</small></summary><button v-for="file in items" :key="file.path" type="button" class="workspace-row" :title="displayPath(file.path)" @click="showPreview(file.path)"><DocDetail /><span><strong>{{ file.name }}</strong><small>{{ file.relative_path || file.path }}</small></span><small v-if="Number.isFinite(file.size)">{{ fileSize(file.size) }}</small></button></details></div>
          <a-empty v-if="!failed && !loading && !directoryGroups.length" :description="t(search ? 'workspace.taskAgentSpace.no_matches' : projectId ? 'workspace.taskAgentSpace.no_project_files' : 'workspace.taskAgentSpace.no_files')" />
          <a-spin v-if="loading && !files.length" />
          <p v-if="limited" class="page-description">{{ t('workspace.taskAgentSpace.files_limited') }}</p>
        </div>
      </template>
      <template v-else-if="current.kind === 'file'">
        <div class="file-toolbar"><span :title="displayPath(current.path)">{{ displayPath(current.path) }}</span><small v-if="readOnlyFile" class="knowledge-readonly">{{ t('workspace.taskAgentSpace.knowledge_readonly') }}</small><IconButton type="text" size="small" :loading="current.loading" :aria-label="t('workspace.taskAgentSpace.refresh_files')" @click="loadPreview(current)" :text="t('workspace.taskAgentSpace.refresh_files')"><template #icon><Refresh /></template></IconButton><IconButton v-if="!readOnlyFile" type="text" size="small" :aria-label="t('workspace.taskAgentSpace.reveal_file')" @click="openFile(true)" :text="t('workspace.taskAgentSpace.reveal_file')"><template #icon><FolderOpen /></template></IconButton><IconButton v-if="!readOnlyFile && fileFor(current).can_open" type="text" size="small" :aria-label="t('workspace.taskAgentSpace.open_file')" @click="openFile(false)" :text="t('workspace.taskAgentSpace.open_file')"><template #icon><OpenExternal /></template></IconButton></div>
        <div v-if="canRenderFile" class="preview-toolbar" role="group" :aria-label="t('workspace.taskAgentSpace.file_view')">
          <a-radio-group v-model:value="current.view" size="small" button-style="solid" :aria-label="t('workspace.taskAgentSpace.file_view')"><a-radio-button value="preview">{{ t('workspace.taskAgentSpace.file_preview') }}</a-radio-button><a-radio-button value="source">{{ t('workspace.taskAgentSpace.file_source') }}</a-radio-button></a-radio-group>
          <span v-if="Number.isFinite(fileFor(current).size)">{{ fileSize(fileFor(current).size) }}</span>
        </div>
        <a-alert v-if="current.error" type="warning" :message="t('workspace.taskAgentSpace.file_failed')"><template #action><IconButton @click="loadPreview(current)" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
        <a-spin v-else-if="current.loading && !current.preview" class="panel-spinner" />
        <div v-else class="file-preview" :class="{ 'html-preview': canRenderFile && !current.preview?.markdown && current.view !== 'source' }">
          <img v-if="current.preview?.kind === 'image'" :src="current.preview.url" :alt="fileFor(current).name" />
          <iframe v-else-if="canRenderFile && !current.preview.markdown && current.view !== 'source'" :title="fileFor(current).name" :srcdoc="htmlPreview" sandbox="" referrerpolicy="no-referrer" />
          <VueMarkdown v-else-if="readOnlyFile && current.preview?.kind === 'text' && current.preview.markdown && current.view !== 'source'" class="markdown-body" :source="current.preview.text" :options="{ html: false, linkify: true }" />
          <TextOutput v-else-if="current.preview?.kind === 'text' && current.preview.markdown && current.view !== 'source'" :text="current.preview.text" :show-copy="false" />
          <pre v-else-if="current.preview?.kind === 'text'">{{ current.preview.text }}</pre>
          <a-empty v-else :description="t('workspace.taskAgentSpace.no_preview')" />
          <p v-if="current.preview?.truncated" class="page-description">{{ t('workspace.taskAgentSpace.preview_limited') }}</p>
        </div>
      </template>
      <div v-else-if="current.kind === 'tool'" class="workspace-page tool-detail">
        <h2>{{ toolTitle(currentTool) }}</h2>
        <p class="page-description">{{ t('workspace.taskAgentSpace.' + toolStatusKey(currentTool)) }}<template v-if="commandStatus(currentTool)"> · {{ t('workspace.taskAgentSpace.command_' + commandStatus(currentTool)) }}</template></p>
        <p v-if="currentTool?.risk_review" class="review-note">{{ t('workspace.taskAgentSpace.risk_status_' + currentTool.risk_review.status) }} · {{ t('workspace.taskAgentSpace.risk_reason_' + (currentTool.risk_review.reason || 'reviewing')) }}<small v-if="currentTool.risk_review.model"> · {{ currentTool.risk_review.model }}</small></p>
        <a-alert v-if="isMcpUnknown(currentTool)" type="warning" show-icon :message="t('workspace.taskAgentSpace.mcp_unknown_hint')" />
        <a-alert v-if="commandStatus(currentTool) === 'unknown'" type="warning" show-icon :message="t('workspace.taskAgentSpace.' + (currentTool.command_status_reason === 'turn_ended_without_terminal_observation' ? 'command_unobserved_hint' : 'command_unknown_hint'))" />
        <a-alert v-if="currentTool?.error_code === 'background_session_missing'" type="warning" show-icon :message="t('workspace.taskAgentSpace.command_handle_missing_hint')" />
        <h3>{{ t('workspace.taskAgentSpace.tool_input') }}</h3>
        <template v-if="currentTool?.tool_name === 'bash' && typeof currentTool.arguments?.command === 'string'">
          <pre class="command-input">{{ currentTool.arguments.command }}</pre>
          <details v-if="Object.keys(extraCommandArguments).length" class="result-details"><summary>{{ t('workspace.taskAgentSpace.command_options') }}</summary><pre>{{ JSON.stringify(extraCommandArguments, null, 2) }}</pre></details>
        </template>
        <pre v-else>{{ JSON.stringify(currentTool?.arguments || {}, null, 2) }}</pre>
        <h3>{{ t('workspace.taskAgentSpace.tool_result') }}</h3>
        <a-alert v-if="current.error" type="warning" :message="t('workspace.taskAgentSpace.result_failed')"><template #action><IconButton @click="readTool(current)" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
        <template v-if="presentedResult.command">
          <dl class="command-facts">
            <div><dt>{{ t('workspace.taskAgentSpace.command_returned_status') }}</dt><dd>{{ t('workspace.taskAgentSpace.command_' + presentedResult.command.status) }}</dd></div>
            <div v-if="presentedResult.command.exit_code != null"><dt>{{ t('workspace.taskAgentSpace.command_exit_code') }}</dt><dd>{{ presentedResult.command.exit_code }}</dd></div>
            <div v-if="presentedResult.command.elapsed_seconds != null"><dt>{{ t('workspace.taskAgentSpace.command_elapsed') }}</dt><dd>{{ presentedResult.command.elapsed_seconds }} s</dd></div>
          </dl>
          <pre v-if="presentedResult.text" class="command-output">{{ presentedResult.text }}</pre><p v-else class="empty-command-output">{{ t('workspace.taskAgentSpace.command_no_output') }}</p>
          <p v-if="presentedResult.command.message" class="page-description">{{ presentedResult.command.message }}</p>
          <p v-if="presentedResult.command.output_truncated" class="page-description">{{ t('workspace.taskAgentSpace.command_output_limited') }}</p>
          <details class="result-details"><summary>{{ t('workspace.taskAgentSpace.raw_result') }}</summary><pre>{{ presentedResult.raw }}</pre></details>
        </template>
        <template v-else-if="presentedResult.mcp">
          <dl class="command-facts">
            <div v-if="presentedResult.mcp.server_name"><dt>{{ t('workspace.taskAgentSpace.mcp_result_server') }}</dt><dd>{{ presentedResult.mcp.server_name }}</dd></div>
            <div v-if="presentedResult.mcp.tool_name"><dt>{{ t('workspace.taskAgentSpace.mcp_result_tool') }}</dt><dd>{{ presentedResult.mcp.tool_name }}</dd></div>
            <div><dt>{{ t('workspace.taskAgentSpace.mcp_result_status') }}</dt><dd>{{ t('workspace.taskAgentSpace.tool_status_' + (['unknown', 'error', 'cancelled', 'running', 'pending', 'success'].includes(presentedResult.mcp.status) ? presentedResult.mcp.status : 'pending')) }}</dd></div>
            <div v-if="presentedResult.mcp.error_code"><dt>{{ t('workspace.taskAgentSpace.mcp_result_diagnostic') }}</dt><dd><code>{{ presentedResult.mcp.error_code }}</code></dd></div>
          </dl>
          <p v-if="presentedResult.mcp.error_message && presentedResult.mcp.error_message !== presentedResult.mcp.text" class="page-description">{{ presentedResult.mcp.error_message }}</p>
          <pre v-if="presentedResult.mcp.text" class="command-output">{{ presentedResult.mcp.text }}</pre>
          <p v-else-if="['pending', 'running'].includes(presentedResult.mcp.status)" class="page-description">{{ t('workspace.taskAgentSpace.result_pending') }}</p>
          <p v-else-if="presentedResult.mcp.structured_content == null && !presentedResult.mcp.artifacts?.length && !presentedResult.mcp.error_message" class="empty-command-output">{{ t('workspace.taskAgentSpace.mcp_result_no_text') }}</p>
          <div v-if="presentedResult.mcp.structured_content != null" class="mcp-structured-section">
            <h4>{{ t('workspace.taskAgentSpace.mcp_result_structured') }}</h4>
            <pre>{{ JSON.stringify(presentedResult.mcp.structured_content, null, 2) }}</pre>
          </div>
          <div v-if="presentedResult.mcp.artifacts?.length" class="mcp-artifacts-section">
            <h4>{{ t('workspace.taskAgentSpace.mcp_result_artifacts') }}</h4>
            <button v-for="artifact in presentedResult.mcp.artifacts" :key="artifact.path" type="button" class="workspace-row" @click="showPreview(artifact.path)">
              <DocDetail />
              <span><strong>{{ artifact.name || artifact.path }}</strong><small>{{ artifact.mime_type }} · {{ fileSize(artifact.byte_size || 0) }}</small></span>
              <span>↗</span>
            </button>
          </div>
          <p v-if="presentedResult.mcp.truncated" class="page-description">{{ t('workspace.taskAgentSpace.mcp_result_truncated') }}</p>
          <details v-if="presentedResult.raw" class="result-details"><summary>{{ t('workspace.taskAgentSpace.raw_result') }}</summary><pre>{{ presentedResult.raw }}</pre></details>
        </template>
        <pre v-else-if="current.text != null || currentTool?.result?.preview">{{ presentedResult.text }}</pre>
        <p v-else class="page-description">{{ t('workspace.taskAgentSpace.result_pending') }}</p>
        <a-spin v-if="current.loading" />
        <IconButton v-if="current.nextOffset != null && !current.error" :loading="current.loading" @click="readTool(current, true)" :text="t('workspace.taskAgentSpace.load_more')"><template #icon><Down /></template></IconButton>
        <p v-if="currentTool?.error_code" class="error-code">{{ currentTool.error_code }}</p>
      </div>
      <div v-else-if="current.kind === 'subtask'" class="workspace-page">
        <h2>{{ tabTitle(current) }}</h2><p class="page-description">{{ t('workspace.taskAgentSpace.child_' + currentChild.status) }}</p>
        <TextOutput v-if="currentChild.final_output" :text="currentChild.final_output" :show-copy="false" />
        <a-alert v-else-if="currentChild.error" type="error" :message="currentChild.error" />
        <p v-else-if="currentChild.status === 'running'" class="page-description"><LoadingFour spin /> {{ t('workspace.taskAgentSpace.child_working') }}</p><a-empty v-else :description="t('workspace.taskAgentSpace.child_no_output')" />
      </div>
      <div v-else-if="current.kind === 'plan'" class="workspace-page">
        <h2>{{ t('workspace.taskAgentSpace.plan') }}</h2><p class="page-description">{{ t('workspace.taskAgentSpace.plan_progress', { done: completed, total: todos.length }) }}</p>
        <ol class="plan-list"><li v-for="(todo, index) in todos" :key="todo.id || index" :class="todo.status"><CheckOne v-if="todo.status === 'completed'" /><LoadingFour v-else-if="todo.status === 'in_progress'" spin /><CircleFourLine v-else /><span>{{ todo.title }}</span></li></ol>
        <a-empty v-if="!todos.length" :description="t('workspace.taskAgentSpace.no_plan')" />
      </div>
      <div v-else-if="current.kind === 'tools'" class="workspace-page"><h2>{{ t('workspace.taskAgentSpace.tools') }}</h2><p class="page-description">{{ t('workspace.taskAgentSpace.tools_description') }}</p><button v-for="entry in tools" :key="entry.id" type="button" class="workspace-row" @click="openTool(entry)"><Tool /><span><strong>{{ toolTitle(entry) }}<em v-if="entry.is_child_session" class="child-session-badge">{{ t('workspace.taskAgentSpace.mcp_child_session_badge') }}</em></strong><small>{{ toolDisplaySummary(entry) || t('workspace.taskAgentSpace.' + toolStatusKey(entry)) }}</small></span><span>↗</span></button><a-empty v-if="!tools.length" :description="t('workspace.taskAgentSpace.no_tools')" /></div>
      <div v-else-if="current.kind === 'subtasks'" class="workspace-page"><h2>{{ t('workspace.taskAgentSpace.subtasks') }}</h2><p class="page-description">{{ t('workspace.taskAgentSpace.subtasks_description') }}</p><button v-for="(entry, index) in children" :key="entry.child_session_id" type="button" class="workspace-row" @click="openSubtask(entry)"><Robot /><span><strong>{{ t('workspace.taskAgentSpace.sub_agent') }} {{ index + 1 }}</strong><small>{{ t('workspace.taskAgentSpace.child_' + entry.status) }}</small></span><span>↗</span></button><a-empty v-if="!children.length" :description="t('workspace.taskAgentSpace.no_subtasks')" /></div>
      <div v-else-if="current.kind === 'agent'" class="workspace-page">
        <h2>{{ profile?.name || t('workspace.taskAgentSpace.general_agent') }}</h2>
        <p class="page-description">{{ t('workspace.taskAgentSpace.snapshot_description') }}</p>
        <p v-if="profile?.permission_mode">{{ t('workspace.taskAgentSpace.permissions') }} · {{ t('workspace.taskAgentSpace.permission_' + profile.permission_mode) }}</p>
        <p v-if="profile?.allow_shell">{{ t('workspace.taskAgentSpace.allow_shell') }} · {{ profile.shell }}</p>
        <p v-if="profile?.allow_sub_agents">{{ t('workspace.taskAgentSpace.allow_sub_agents') }} · worker</p>
        <div v-if="workflows.length">
          <h3>{{ t('workspace.taskAgentSpace.workflows') }}</h3>
          <p v-for="workflow in workflows" :key="workflow.workflow_id">{{ workflow.title }} · v{{ workflow.version }}</p>
        </div>
        <div v-if="skills.length" class="snapshot-section">
          <h3>{{ t('workspace.taskAgentSpace.snapshot_skills_title') }}</h3>
          <p class="page-description">{{ t('workspace.taskAgentSpace.snapshot_skills_hint') }}</p>
          <div v-for="skill in skills" :key="`${skill.skill_id}@${skill.version}`" class="workspace-row snapshot-item-row">
            <DocDetail />
            <span>
              <strong>{{ skill.name || skill.skill_id }} · v{{ skill.version }}</strong>
              <small v-if="skill.description">{{ skill.description }}</small>
            </span>
            <router-link :to="{ name: 'taskAgentSkillDetail', params: { skillId: skill.skill_id }, query: { version: String(skill.version) } }" class="snapshot-skill-link">{{ t('workspace.taskAgentSpace.snapshot_inspect_skill', { version: skill.version }) }}</router-link>
          </div>
        </div>
        <div v-if="mcpTools.length" class="snapshot-section">
          <h3>{{ t('workspace.taskAgentSpace.snapshot_mcp_title') }}</h3>
          <p class="page-description">{{ t('workspace.taskAgentSpace.snapshot_mcp_hint') }}</p>
          <div v-for="mcpTool in mcpTools" :key="mcpTool.namespaced_name" class="workspace-row snapshot-item-row">
            <Tool />
            <span>
              <strong>{{ mcpTool.server_name || mcpTool.server_id }}: {{ mcpTool.title || mcpTool.name }}</strong>
              <small>{{ mcpTool.name }}<template v-if="mcpTool.description"> — {{ mcpTool.description }}</template></small>
            </span>
          </div>
        </div>
        <p class="profile-instructions">{{ profile?.instructions || t('workspace.taskAgentSpace.general_description') }}</p>
      </div>
      <div v-else class="workspace-page workspace-home"><p class="page-description">{{ t('workspace.taskAgentSpace.workspace') }}</p><h2>{{ t('workspace.taskAgentSpace.choose_workspace_content') }}</h2><p class="page-description">{{ t('workspace.taskAgentSpace.workspace_hint') }}</p><div class="workspace-launchers"><button v-for="kind in ['files', 'plan', 'subtasks', 'tools', 'agent']" :key="kind" type="button" class="workspace-launcher" @click="launch(kind)"><component :is="tabIcon({ kind })" size="21" /><span><strong>{{ t('workspace.taskAgentSpace.' + kind) }}</strong><small>{{ t('workspace.taskAgentSpace.workspace_' + kind + '_hint') }}</small></span><span>↗</span></button></div></div>
    </section>
  </aside>
</template>
<style scoped>
.knowledge-readonly { flex-shrink: 0; color: var(--site-secondary-text-color); font-size: 12px; }
.project-root-select { width: 100%; margin-bottom: 12px; }

.workspace-panel { --workspace-bg: var(--component-background, #fff); --workspace-chrome: var(--gray-background, #f7f8fa); --workspace-line: var(--border-color-base, #e5e8eb); display: flex; flex-direction: column; flex: 0 0 60%; min-width: 0; min-height: 0; height: 100%; border-left: 1px solid var(--workspace-line); background: var(--workspace-bg); color: var(--site-text-color); overflow: hidden; }
.workspace-expanded { position: absolute; inset: 0; z-index: 30; width: 100%; }
.workspace-tabbar { display: flex; align-items: center; gap: 4px; height: 48px; flex: 0 0 auto; padding: 6px 8px; border-bottom: 1px solid var(--workspace-line); background: var(--workspace-chrome); }
.workspace-tablist { display: flex; align-items: center; gap: 3px; min-width: 0; overflow-x: auto; }
.workspace-tab { display: flex; align-items: center; max-width: 210px; flex: 0 0 auto; height: 33px; border: 1px solid transparent; border-radius: 6px; }
.workspace-tab.active { border-color: var(--workspace-line); background: var(--workspace-bg); box-shadow: 0 1px 2px #00000004; }
.workspace-tab > button:first-child { display: flex; align-items: center; gap: 7px; min-width: 0; height: 100%; padding: 0 9px; border: 0; background: none; color: inherit; font-size: 12px; cursor: pointer; white-space: nowrap; }
.workspace-tab > button:first-child > span { overflow: hidden; text-overflow: ellipsis; }
.workspace-tab svg { flex-shrink: 0; }
:deep(.tab-close), :deep(.workspace-icon-button) { display: grid; place-items: center; flex: 0 0 auto; padding: 0; border: 0; border-radius: 4px; background: none; color: var(--site-secondary-text-color); cursor: pointer; }
:deep(.tab-close) { margin-right: 3px; }
.workspace-actions { display: flex; gap: 2px; margin-left: auto; }
.workspace-body { flex: 1; min-height: 0; overflow: auto; overscroll-behavior: contain; }
.workspace-page { max-width: 820px; margin: 0 auto; padding: 35px 38px 48px; }.workspace-page.tool-detail { padding: 18px; }
h2 { margin: 0 0 12px; font-size: 22px; line-height: 1.5; font-weight: 600; }h3 { margin: 24px 0 10px; font-size: 14px; font-weight: 500; }
.page-heading { display: flex; align-items: center; justify-content: space-between; }.page-heading h2 { margin-bottom: 0; }
.page-description { font-size: 13px; line-height: 1.65; color: var(--site-secondary-text-color); }
.workspace-row, .workspace-launcher { display: flex; align-items: center; gap: 12px; width: 100%; padding: 12px 8px; border: 0; border-bottom: 1px solid var(--workspace-line); background: transparent; color: inherit; text-align: left; cursor: pointer; }
.workspace-row > svg, .workspace-launcher > svg { flex-shrink: 0; color: var(--site-secondary-text-color); }.workspace-row > span:first-of-type, .workspace-launcher > span:first-of-type { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.workspace-row strong, .workspace-row small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.workspace-row strong, .workspace-launcher strong { font-size: 13px; font-weight: 500; }.workspace-row small, .workspace-launcher small { font-size: 12px; color: var(--site-secondary-text-color); }
.file-groups { margin-top: 20px; }.file-groups summary { padding: 8px 0; font-size: 12px; color: var(--site-secondary-text-color); cursor: pointer; }.file-groups summary small { margin-left: 8px; font-variant-numeric: tabular-nums; }
.file-toolbar { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; gap: 8px; padding: 10px 16px; background: var(--workspace-bg); border-bottom: 1px solid var(--workspace-line); }.file-toolbar > span:not(.icon-button-root):not(.icon-button-trigger) { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: var(--site-secondary-text-color); }
.preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; border-bottom: 1px solid var(--workspace-line); }.preview-toolbar > span { color: var(--site-secondary-text-color); font-size: 12px; }
.file-preview.html-preview { max-width: none; height: calc(100% - 96px); min-height: 450px; padding: 12px; }.html-preview iframe { width: 100%; height: 100%; min-height: 420px; border: 1px solid var(--workspace-line); border-radius: 6px; background: #fff; }
.command-facts { display: flex; flex-wrap: wrap; gap: 12px 24px; margin: 0 0 16px; padding: 12px 0; border-block: 1px solid var(--workspace-line); }.command-facts > div { display: flex; align-items: center; gap: 8px; font-size: 12px; }.command-facts dt { color: var(--site-secondary-text-color); }.command-facts dd { margin: 0; font-variant-numeric: tabular-nums; }.command-output { min-height: 70px; }.empty-command-output { padding: 18px 14px; border: 1px solid var(--workspace-line); border-radius: 6px; color: var(--site-secondary-text-color); font-size: 13px; }.result-details { margin-top: 12px; }.result-details summary { cursor: pointer; color: var(--site-secondary-text-color); font-size: 12px; }.result-details pre { margin-top: 10px; }
.file-preview { padding: 34px 40px 55px; max-width: 800px; margin: 0 auto; }.file-preview img { display: block; max-width: 100%; height: auto; margin: auto; }.file-preview :deep(.markdown-body) { font-family: inherit; font-size: 14px; line-height: 1.9; background: transparent; }.file-preview :deep(h1) { font-size: 27px; line-height: 1.5; border: 0; padding: 0; margin-bottom: 18px; }.file-preview :deep(h2) { font-size: 17px; border: 0; padding: 0; margin-top: 30px; }.file-preview :deep(table) { display: table; width: 100%; font-size: 12px; }.file-preview :deep(th) { font-weight: 500; background: var(--workspace-chrome); }.file-preview :deep(th), .file-preview :deep(td) { padding: 10px 12px; border-inline: 0; border-color: var(--workspace-line); }
pre { padding: 14px; border: 1px solid var(--workspace-line); border-radius: 6px; background: var(--workspace-chrome); font-size: 12px; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.panel-spinner { display: block; margin: 36px auto; }.review-note { padding: 10px 0; font-size: 13px; color: var(--site-secondary-text-color); }.error-code { color: var(--error-color, #cf4545); }
.plan-list { list-style: none; padding: 0; }.plan-list li { display: flex; align-items: baseline; gap: 12px; padding: 14px 0; font-size: 14px; border-bottom: 1px solid var(--workspace-line); }.plan-list li > svg { flex-shrink: 0; }.plan-list .completed { color: var(--site-secondary-text-color); }.plan-list .in_progress { font-weight: 500; }
.profile-instructions { white-space: pre-wrap; line-height: 1.75; }
.snapshot-section { margin: 16px 0; }
.snapshot-item-row { cursor: default; }
.snapshot-skill-link { font-size: 12px; color: var(--color-primary); white-space: nowrap; }
.mcp-structured-section, .mcp-artifacts-section { margin-top: 14px; }
.mcp-structured-section h4, .mcp-artifacts-section h4 { margin: 0 0 8px; font-size: 13px; font-weight: 500; }.workspace-launchers { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 9px; }.workspace-launcher { padding: 16px 13px; border: 1px solid var(--workspace-line); border-radius: 7px; }.workspace-home { max-width: 680px; margin: auto; }
button:focus-visible, summary:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
@media (hover: hover) and (pointer: fine) { .workspace-row:hover, .workspace-launcher:hover, :deep(.workspace-icon-button):hover, :deep(.tab-close):hover, .workspace-tab:not(.active):hover { background: var(--more-hover-background); } }
.theme-dark .workspace-panel { --workspace-line: #30363b; }
@media (max-width: 900px) { .workspace-page { padding: 24px 20px; }.preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; border-bottom: 1px solid var(--workspace-line); }.preview-toolbar > span { color: var(--site-secondary-text-color); font-size: 12px; }
.file-preview.html-preview { max-width: none; height: calc(100% - 96px); min-height: 450px; padding: 12px; }.html-preview iframe { width: 100%; height: 100%; min-height: 420px; border: 1px solid var(--workspace-line); border-radius: 6px; background: #fff; }
.command-facts { display: flex; flex-wrap: wrap; gap: 12px 24px; margin: 0 0 16px; padding: 12px 0; border-block: 1px solid var(--workspace-line); }.command-facts > div { display: flex; align-items: center; gap: 8px; font-size: 12px; }.command-facts dt { color: var(--site-secondary-text-color); }.command-facts dd { margin: 0; font-variant-numeric: tabular-nums; }.command-output { min-height: 70px; }.empty-command-output { padding: 18px 14px; border: 1px solid var(--workspace-line); border-radius: 6px; color: var(--site-secondary-text-color); font-size: 13px; }.result-details { margin-top: 12px; }.result-details summary { cursor: pointer; color: var(--site-secondary-text-color); font-size: 12px; }.result-details pre { margin-top: 10px; }
.file-preview { padding-inline: 20px; }.file-toolbar { flex-wrap: wrap; }.file-toolbar > span:not(.icon-button-root):not(.icon-button-trigger) { flex-basis: 100%; } }
.child-session-badge { display: inline-block; margin-left: 6px; padding: 0 5px; border-radius: 4px; background: var(--gray-background); font-style: normal; font-size: 10px; font-weight: 500; color: var(--site-secondary-text-color); }
</style>
