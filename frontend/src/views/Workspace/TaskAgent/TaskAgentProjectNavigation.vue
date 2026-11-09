<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message, theme } from 'ant-design-vue'
import { PhPushPin } from '@phosphor-icons/vue'
import { FolderOpen, Plus, Down, Edit, ListOne, LoadingFour, Refresh, Delete } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { taskNeedsPolling } from '@/utils/taskAgentTimeline'
import { taskStatusClass } from '@/utils/taskAgentPresentation'
import TaskAgentProjectEditor from '@/views/Workspace/TaskAgent/TaskAgentProjectEditor.vue'

const props = defineProps({ activeProjectId: { type: String, default: '' } })
const emit = defineEmits(['deleted'])
const { t } = useI18n()
const { token } = theme.useToken()
const route = useRoute(), router = useRouter()
const projects = ref([]), loading = ref(false), failed = ref(false)
const expanded = reactive(new Set()), pages = reactive({})
const editing = ref(null), editorOpen = ref(false), popover = ref('')
const pinned = ref([])
const pendingDelete = ref(null), deleting = ref(false), deleteError = ref('')
const askDelete = project => { popover.value = ''; pendingDelete.value = { ...project }; deleteError.value = '' }
const confirmDelete = async () => {
  const target = pendingDelete.value
  if (!target || deleting.value) return
  deleting.value = true; deleteError.value = ''
  try {
    const response = await taskAgentAPI('delete_project', { project_id: target.project_id, expected_updated_at: target.updated_at, expected_task_count: target.task_count })
    if (!alive) return
    if (response.status !== 200 && response.status !== 404) { deleteError.value = response.data?.deletion_error || 'failed'; return }
    expanded.delete(target.project_id); delete pages[target.project_id]
    pinned.value = pinned.value.filter(id => id !== target.project_id)
    try {
      localStorage.setItem('task-agent-pinned-projects', JSON.stringify(pinned.value))
      const favorites = JSON.parse(localStorage.getItem('task-agent-favorite-tasks') || '[]')
      if (Array.isArray(favorites)) localStorage.setItem('task-agent-favorite-tasks', JSON.stringify(favorites.filter(id => !response.data?.task_ids?.includes(id))))
    } catch { /* Storage is optional. */ }
    pendingDelete.value = null
    emit('deleted', { project_id: target.project_id, task_ids: response.data?.task_ids || [] })
    message.success(t('workspace.taskAgentSpace.project_deleted'))
    if (props.activeProjectId === target.project_id || route.params.projectId === target.project_id || route.query.project_id === target.project_id || response.data?.task_ids?.includes(route.params.taskId)) await router.replace({ name: 'taskAgentWorkbench' })
    await refresh()
  } catch { if (alive) deleteError.value = 'failed' }
  finally { if (alive) deleting.value = false }
}
const viewTasks = project => { popover.value = ''; router.push({ name: 'taskAgentTasks', query: { project_id: project.project_id } }) }
try {
  const saved = JSON.parse(localStorage.getItem('task-agent-pinned-projects') || '[]')
  if (Array.isArray(saved)) pinned.value = saved.filter(value => typeof value === 'string')
} catch { /* Storage is optional. */ }
const orderedProjects = computed(() => {
  const order = new Map(pinned.value.map((id, index) => [id, index]))
  return [...projects.value].sort((a, b) => (order.get(a.project_id) ?? Infinity) - (order.get(b.project_id) ?? Infinity))
})
let alive = true, version = 0, request = 0, timer = null
const schedule = () => {
  if (timer !== null) window.clearTimeout(timer)
  if (alive && (failed.value || [...expanded].some(id => pages[id]?.error || pages[id]?.tasks.some(task => taskNeedsPolling(task.status))))) {
    timer = window.setTimeout(() => refresh(), 5000)
  }
}
const loadTasks = async (id, append = false) => {
  if (!pages[id]) pages[id] = { tasks: [], offset: 0, more: false, loading: false, error: false, request: 0 }
  const page = pages[id]
  if (append && page.loading) return
  const current = ++request
  page.request = current; page.loading = true; page.error = false
  const limit = append ? 5 : Math.min(100, Math.max(5, page.tasks.length))
  try {
    const response = await taskAgentAPI('list', { project_id: id, limit, offset: append ? page.offset : 0 })
    if (!alive || page.request !== current) return
    if (response.status !== 200 || response.data.sync_error) throw new Error()
    const incoming = response.data.tasks
    page.tasks = append ? [...new Map([...page.tasks, ...incoming].map(task => [task.tid, task])).values()] : incoming
    page.offset = append ? page.offset + incoming.length : incoming.length
    page.more = incoming.length === limit && page.offset < (projects.value.find(project => project.project_id === id)?.task_count ?? Infinity)
  } catch { if (alive && page.request === current) page.error = true }
  finally { if (alive && page.request === current) { page.loading = false; schedule() } }
}
const refresh = async (force = true) => {
  const current = ++version
  loading.value = true; failed.value = false
  try {
    const response = await taskAgentAPI('projects')
    if (!alive || current !== version) return
    if (response.status !== 200) throw new Error()
    const previous = new Map(projects.value.map(project => [project.project_id, project.task_count]))
    projects.value = response.data.projects
    await Promise.all(projects.value.filter(project => expanded.has(project.project_id) && (force || !pages[project.project_id] || previous.get(project.project_id) !== project.task_count)).map(project => loadTasks(project.project_id)))
  } catch { if (alive && current === version) failed.value = true }
  finally { if (alive && current === version) { loading.value = false; schedule() } }
}
const toggle = id => {
  if (expanded.has(id)) expanded.delete(id)
  else { expanded.add(id); if (!pages[id] || pages[id].error) loadTasks(id) }
  schedule()
}
const openProject = id => { popover.value = ''; expanded.add(id); router.push({ name: 'taskAgentProject', params: { projectId: id } }) }
const edit = project => { popover.value = ''; editing.value = project; editorOpen.value = true }
const saved = project => { if (!editing.value) openProject(project.project_id) }
const togglePin = id => {
  pinned.value = pinned.value.includes(id) ? pinned.value.filter(value => value !== id) : [id, ...pinned.value]
  try { localStorage.setItem('task-agent-pinned-projects', JSON.stringify(pinned.value)) } catch { /* Storage is optional. */ }
}
watch(() => props.activeProjectId, id => {
  if (!id) return
  expanded.add(id)
  if (!pages[id]) loadTasks(id)
}, { immediate: true })
watch(() => route.fullPath, () => { popover.value = ''; refresh(false) })
onMounted(refresh)
onBeforeUnmount(() => { alive = false; version++; if (timer !== null) window.clearTimeout(timer) })
defineExpose({ refresh })
</script>

<template>
  <section class="project-navigation" :aria-label="t('workspace.taskAgentSpace.all_projects')" :aria-busy="loading">
    <header class="project-section-title"><span>{{ t('workspace.taskAgentSpace.all_projects') }}</span><IconButton class="project-icon-button" :aria-label="t('workspace.taskAgentSpace.create_project')" @click="edit(null)" size="small" :text="t('workspace.taskAgentSpace.create_project')"><template #icon><Plus /></template></IconButton></header>
    <div v-if="failed" class="project-list-notice"><span>{{ t('workspace.taskAgentSpace.project_load_failed') }}</span><IconButton size="small" :loading="loading" :text="t('workspace.taskAgentSpace.retry')" @click="refresh()"><template #icon><Refresh /></template></IconButton></div>
    <span v-if="loading && !projects.length" class="project-list-notice"><LoadingFour spin />{{ t('workspace.taskAgentSpace.loading_projects') }}</span>
    <button v-else-if="!failed && !projects.length" type="button" class="project-list-notice" @click="edit(null)">{{ t('workspace.taskAgentSpace.no_sidebar_projects') }}</button>
    <div v-for="project in orderedProjects" :key="project.project_id" class="project-tree-group">
      <div class="project-row" :class="{ active: activeProjectId === project.project_id }">
        <IconButton class="project-tree-toggle" :aria-label="t('workspace.taskAgentSpace.toggle_project', { name: project.name })" :aria-expanded="expanded.has(project.project_id)" @click="toggle(project.project_id)" size="small" :text="t('workspace.taskAgentSpace.toggle_project', { name: project.name })"><template #icon><Down :class="{ collapsed: !expanded.has(project.project_id) }" /></template></IconButton>
        <a-popover :trigger="['hover', 'focus']" placement="rightTop" :align="{ offset: [24, -12] }" :mouse-enter-delay="0.25" :mouse-leave-delay="0.15" :open="popover === project.project_id" @open-change="popover = $event ? project.project_id : ''">
          <button type="button" class="project-link" :title="project.name" @click="openProject(project.project_id)"><FolderOpen /><span>{{ project.name }}</span><small>{{ project.task_count }}</small></button>
          <template #content>
            <div class="project-quick-card" :style="{ '--project-card-secondary': token.colorTextSecondary }">
              <header><span class="project-card-title"><FolderOpen /><strong>{{ project.name }}</strong></span><IconButton type="text" size="small" class="project-card-edit" :text="t('workspace.taskAgentSpace.edit_project') + ' ' + project.name" @click="edit(project)"><template #icon><Edit /></template></IconButton><IconButton type="text" class="project-icon-button" :class="{ pinned: pinned.includes(project.project_id) }" :aria-label="t('workspace.taskAgentSpace.' + (pinned.includes(project.project_id) ? 'unpin_project' : 'pin_project'))" :aria-pressed="pinned.includes(project.project_id)" @click="togglePin(project.project_id)" :text="t('workspace.taskAgentSpace.' + (pinned.includes(project.project_id) ? 'unpin_project' : 'pin_project'))"><template #icon><PhPushPin :weight="pinned.includes(project.project_id) ? 'fill' : 'regular'" /></template></IconButton></header>
              <a-button type="text" class="project-card-meta" block @click="viewTasks(project)"><template #icon><ListOne /></template>{{ t('workspace.taskAgentSpace.task_count', { count: project.task_count }) }}</a-button>
              <div class="project-card-meta"><FolderOpen />{{ t('workspace.taskAgentSpace.project_folder_count', { count: project.roots.length }) }}</div>
              <p v-for="folder in project.folders" :key="folder.id" class="project-card-folder" :class="{ unavailable: !folder.available }">{{ folder.path }}</p>
              <IconButton type="text" class="project-card-delete" danger @click="askDelete(project)" :text="t('workspace.taskAgentSpace.delete_project')"><template #icon><Delete /></template></IconButton>
            </div>
          </template>
        </a-popover>
        <IconButton class="project-new-task project-icon-button" :aria-label="t('workspace.taskAgentSpace.new_project_task', { name: project.name })" @click="openProject(project.project_id)" size="small" :text="t('workspace.taskAgentSpace.new_project_task', { name: project.name })"><template #icon><Plus /></template></IconButton>
      </div>
      <div v-if="expanded.has(project.project_id)" class="project-task-tree">
        <router-link v-for="task in pages[project.project_id]?.tasks || []" :key="task.tid" class="project-task-link" :class="{ active: route.params.taskId === task.tid }" :to="{ name: 'taskAgentDetail', params: { taskId: task.tid } }" :title="task.title"><span>{{ task.title }}</span><LoadingFour v-if="['PROCESSING', 'PENDING'].includes(task.status)" spin :aria-label="t('workspace.taskAgentSpace.status_' + task.status)" /><i v-else-if="['WAITING_FOR_USER', 'WAITING_FOR_APPROVAL', 'WAITING_FOR_WORKFLOW', 'FAILED', 'INTERRUPTED', 'PAUSED'].includes(task.status)" class="task-state" :class="taskStatusClass(task.status)" role="img" :aria-label="t('workspace.taskAgentSpace.status_' + task.status)" /></router-link>
        <span v-if="pages[project.project_id]?.loading && !pages[project.project_id]?.tasks.length" class="project-list-notice"><LoadingFour spin /></span>
        <IconButton v-if="pages[project.project_id]?.error" class="project-load-more" :disabled="pages[project.project_id].loading" @click="loadTasks(project.project_id)" size="small" :text="t('workspace.taskAgentSpace.retry_project_tasks')"><template #icon><Refresh /></template></IconButton>
        <IconButton v-else-if="pages[project.project_id]?.more" class="project-load-more" :disabled="pages[project.project_id].loading" @click="loadTasks(project.project_id, true)" size="small" :text="t('workspace.taskAgentSpace.load_more')"><template #icon><LoadingFour v-if="pages[project.project_id].loading" spin /><Down v-else /></template></IconButton>
        <span v-else-if="pages[project.project_id] && !pages[project.project_id].loading && !pages[project.project_id].tasks.length" class="project-list-notice">{{ t('workspace.taskAgentSpace.no_project_tasks') }}</span>
      </div>
    </div>
    <TaskAgentProjectEditor v-model:open="editorOpen" :project="editing" @saved="saved" />
    <a-modal :open="!!pendingDelete" :title="t('workspace.taskAgentSpace.delete_project')" :ok-text="t('common.delete')" :cancel-text="t('common.cancel')" :ok-button-props="{ danger: true }" :confirm-loading="deleting" :cancel-button-props="{ disabled: deleting }" :closable="!deleting" :keyboard="!deleting" :mask-closable="false" @ok="confirmDelete" @cancel="!deleting && (pendingDelete = null)">
      <p>{{ t('workspace.taskAgentSpace.delete_project_confirm', { name: pendingDelete?.name || '', count: pendingDelete?.task_count || 0 }) }}</p>
      <a-alert v-if="deleteError" type="error" show-icon :message="t('workspace.taskAgentSpace.delete_error_' + deleteError)" />
    </a-modal>
  </section>
</template>

<style scoped>
.project-navigation { min-height: 0; overflow-y: auto; padding: 12px 8px 20px; border-top: var(--light-border); }
.project-section-title { display: flex; justify-content: space-between; align-items: center; padding: 0 2px 6px; color: var(--site-secondary-text-color); font-size: 12px; }
button:not(.ant-btn) { font: inherit; cursor: pointer; color: inherit; border: 0; background: transparent; }
button:not(.ant-btn):disabled { cursor: default; opacity: .5; }
:deep(.project-icon-button) { display: inline-grid; place-items: center; flex-shrink: 0; border-radius: 5px; }
.project-row { display: flex; align-items: center; min-height: 34px; gap: 2px; border-radius: 6px; }
.project-row.active, .project-task-link.active { background: color-mix(in srgb, var(--color-primary) 12%, transparent); color: var(--color-primary); }
:deep(.project-tree-toggle) { display: grid; place-items: center; flex-shrink: 0; padding: 0; color: var(--site-secondary-text-color); }
:deep(.project-tree-toggle) svg { width: 12px; height: 12px; }:deep(.project-tree-toggle) .collapsed { transform: rotate(-90deg); }
.project-link { display: flex; flex: 1; min-width: 0; align-items: center; gap: 7px; padding: 6px 0; text-align: left; font-size: 13px; }
.project-link > svg { width: 14px; height: 14px; flex-shrink: 0; }
.project-link > span, .project-task-link > span { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.project-link small { color: var(--site-secondary-text-color); font-size: 11px; }
:deep(.project-new-task) { color: var(--color-primary); }
.project-task-tree { padding: 2px 0 5px 30px; }
.project-task-link { display: flex; align-items: center; gap: 6px; min-height: 30px; padding: 4px 7px; border-radius: 5px; color: var(--site-text-color); font-size: 12px; text-decoration: none; }
.project-task-link > svg { flex-shrink: 0; width: 12px; height: 12px; color: var(--site-secondary-text-color); }
.task-state { flex-shrink: 0; width: 6px; height: 6px; border-radius: 50%; background: #d48806; }.status-failed { background: #ff4d4f; }.status-paused { background: #8c8c8c; }
.project-list-notice, :deep(.project-load-more) { display: flex; align-items: center; gap: 6px; padding: 6px; color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.5; }
.project-quick-card { width: 270px; max-width: calc(100vw - 64px); padding: 4px; color: inherit; }
.project-quick-card header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.project-card-title { display: flex; flex: 1; min-width: 0; align-items: center; gap: 8px; }.project-card-title strong { min-width: 0; overflow-wrap: anywhere; font-size: 14px; }.project-card-title > svg { flex-shrink: 0; }
.project-quick-card :deep(.ant-btn.project-icon-button) { padding: 0; }
.project-quick-card .ant-btn.project-card-meta, :deep(.project-card-delete) { display: flex; align-items: center; justify-content: flex-start; gap: 8px; padding: 4px 6px; }
.project-card-meta { display: flex; align-items: center; gap: 8px; padding: 6px 0; color: inherit; font-size: 13px; text-align: left; text-decoration: none; }.project-card-folder { margin: 3px 0 7px 22px; overflow-wrap: anywhere; font-size: 12px; color: var(--project-card-secondary); }.project-card-folder.unavailable { color: #d48806; }
:deep(.project-icon-button).pinned { color: var(--color-primary, #28c5e5); }
button:focus-visible, a:focus-visible { outline: 2px solid var(--color-primary, #28c5e5); outline-offset: -2px; }
@media (hover: hover) and (pointer: fine) { :deep(.project-new-task) { opacity: 0; }.project-row:hover :deep(.project-new-task), .project-row:focus-within :deep(.project-new-task) { opacity: 1; }.project-row:not(.active):hover, .project-task-link:not(.active):hover, :deep(.project-icon-button):hover { background: var(--more-hover-background); } }
</style>
