<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { Plus, Search, Robot, Control, ListOne, ViewGridCard, PreviewOpen, PreviewCloseOne, Star, Delete, Close, Refresh } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import AgentPicker from '@/components/taskAgent/AgentPicker.vue'
import { taskStatusClass } from '@/utils/taskAgentPresentation'
import { taskNeedsPolling } from '@/utils/taskAgentTimeline'

const { t, locale } = useI18n()
const router = useRouter(), route = useRoute()
const projectId = computed(() => String(route.query.project_id || ''))
const project = ref(null), tasks = ref([]), agents = ref([]), total = ref(0)
const loading = ref(false), failed = ref(false), selected = ref([])
const visibility = computed(() => ['hidden', 'all'].includes(route.query.visibility) ? route.query.visibility : 'visible')
const changingVisibility = ref(null)
const toggleHidden = async task => {
  if (changingVisibility.value) return
  changingVisibility.value = task.tid
  try {
    const response = await taskAgentAPI('set_hidden', { task_id: task.tid, hidden: !task.hidden, expected_updated_at: task.updated_at })
    if (!alive) return
    if (response.status !== 200) { message.error(t('workspace.taskAgentSpace.visibility_failed')); return }
    refreshProjects?.()
    await loadTasks()
  } catch { if (alive) message.error(t('workspace.taskAgentSpace.visibility_failed')) }
  finally { if (alive) changingVisibility.value = null }
}
const pendingDelete = ref(null), deleting = ref(false), deleteError = ref('')
const refreshProjects = inject('refreshTaskAgentProjects', null)
const projectDeletion = inject('taskAgentProjectDeletion', ref(null))
const askDelete = task => { pendingDelete.value = { ...task }; deleteError.value = '' }
const confirmDelete = async () => {
  const task = pendingDelete.value
  if (!task || deleting.value) return
  deleting.value = true; deleteError.value = ''
  try {
    const response = await taskAgentAPI('delete_task', { task_id: task.tid, expected_updated_at: task.updated_at })
    if (!alive) return
    if (response.status !== 200 && response.status !== 404) { deleteError.value = response.data?.deletion_error || 'failed'; return }
    saveFavorites(favorites.value.filter(id => id !== task.tid))
    selected.value = selected.value.filter(id => id !== task.tid)
    pendingDelete.value = null
    message.success(t('workspace.taskAgentSpace.task_deleted'))
    refreshProjects?.()
    await loadTasks()
  } catch { if (alive) deleteError.value = 'failed' }
  finally { if (alive) deleting.value = false }
}
const search = ref(String(route.query.search || ''))
const statusValues = ['PENDING', 'PROCESSING', 'WAITING_FOR_USER', 'WAITING_FOR_APPROVAL', 'WAITING_FOR_WORKFLOW', 'COMPLETED', 'PAUSED', 'FAILED', 'INTERRUPTED']
const statuses = computed(() => String(route.query.status || '').split(',').filter(value => statusValues.includes(value)))
const agentId = computed(() => String(route.query.agent_id || '') || undefined)
const page = computed(() => Math.max(1, Number.parseInt(route.query.page, 10) || 1))
const pageSize = computed(() => [10, 20, 50, 100].includes(Number(route.query.page_size)) ? Number(route.query.page_size) : 10)
const sortBy = computed(() => route.query.sort === 'updated_at' ? 'updated_at' : 'created_at')
const sortOrder = computed(() => route.query.order === 'asc' ? 'asc' : 'desc')
const filterOpen = ref(statuses.value.length > 0)
const favorites = ref([]), savedView = ref('list')
try {
  const saved = JSON.parse(localStorage.getItem('task-agent-favorite-tasks') || '[]')
  if (Array.isArray(saved)) favorites.value = saved.filter(value => typeof value === 'string')
  savedView.value = localStorage.getItem('task-agent-task-view') === 'card' ? 'card' : 'list'
} catch { /* Storage is optional. */ }
const view = computed(() => ['list', 'card'].includes(route.query.view) ? route.query.view : savedView.value)
const filtered = computed(() => Boolean(route.query.search || agentId.value || statuses.value.length))
const agentName = profile => profile?.name || (profile?.agent_id && profile.agent_id !== 'general' ? profile.agent_id : t('workspace.taskAgentSpace.general_agent'))
const profileOf = task => task.config_snapshot?.agent_profile
const projectName = task => task.config_snapshot?.project?.name || t('workspace.taskAgentSpace.task_without_project')
const isFavorite = task => favorites.value.includes(task.tid)
const saveFavorites = ids => {
  favorites.value = ids
  try { localStorage.setItem('task-agent-favorite-tasks', JSON.stringify(ids)) } catch { /* Storage is optional. */ }
}
const toggleFavorite = task => saveFavorites(isFavorite(task) ? favorites.value.filter(id => id !== task.tid) : [...favorites.value, task.tid])
const favoriteSelected = () => { saveFavorites([...new Set([...favorites.value, ...selected.value])]); selected.value = [] }
const updateQuery = patch => {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (!query[key] || (key === 'page' && Number(query[key]) === 1)) delete query[key]
  return router.replace({ name: 'taskAgentTasks', query })
}
const changeView = value => {
  savedView.value = value
  try { localStorage.setItem('task-agent-task-view', value) } catch { /* Storage is optional. */ }
  updateQuery({ view: value, page: undefined })
}
const clearFilters = () => { search.value = ''; updateQuery({ search: undefined, agent_id: undefined, status: undefined, page: undefined }) }
const taskRoute = task => ({ name: 'taskAgentDetail', params: { taskId: task.tid } })
const openTask = (task, event) => {
  if (event.defaultPrevented || event.button > 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey ||
    event.target.closest?.('a, button, input, label, select, textarea, [role="button"], [role="checkbox"], .ant-table-selection-column')) return
  return router.push(taskRoute(task))
}
const createRoute = computed(() => ({ name: projectId.value ? 'taskAgentProject' : 'taskAgentWorkbench',
  ...(projectId.value ? { params: { projectId: projectId.value } } : {}), query: agentId.value ? { agent_id: agentId.value } : {} }))
const dateLabel = value => {
  if (!value || Number.isNaN(Date.parse(value))) return '—'
  return new Intl.DateTimeFormat(locale.value, { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}
const statusColor = value => ({ 'status-completed': 'green', 'status-processing': 'cyan', 'status-pending': 'gold', 'status-attention': 'gold', 'status-failed': 'red' }[taskStatusClass(value)])
const columns = computed(() => [
  { title: t('workspace.taskAgentSpace.task_title'), key: 'title', width: 220, ellipsis: true },
  { title: t('workspace.taskAgentSpace.source_agent'), key: 'agent', width: 140, ellipsis: true },
  { title: t('common.status'), dataIndex: 'status', key: 'status', width: 100, filters: statusValues.map(value => ({ text: t('workspace.taskAgentSpace.status_' + value), value })), filteredValue: statuses.value },
  { title: t('workspace.taskAgentSpace.projects'), key: 'project', width: 88, ellipsis: true },
  { title: t('workspace.taskAgentSpace.current_cycle'), dataIndex: 'current_cycle_index', key: 'cycle', width: 88, align: 'center' },
  { title: t('common.model'), dataIndex: 'model', key: 'model', width: 100, ellipsis: true },
  ...['created_at', 'updated_at'].map(key => ({ title: t(key === 'created_at' ? 'common.create_time' : 'common.update_time'), key, dataIndex: key, width: 140, sorter: true, sortOrder: sortBy.value === key ? (sortOrder.value === 'asc' ? 'ascend' : 'descend') : null })),
  { title: t('common.action'), key: 'action', width: 160, align: 'center', fixed: 'right' },
])
const pagination = computed(() => ({ current: page.value, pageSize: pageSize.value, total: total.value, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'], hideOnSinglePage: false }))
const tableChange = (next, filters, sorter) => updateQuery({ page: String(next.current), page_size: String(next.pageSize),
  status: filters.status?.join(',') || undefined, sort: sorter.order ? sorter.columnKey : 'created_at', order: sorter.order === 'ascend' ? 'asc' : undefined })
const request = computed(() => ({ limit: pageSize.value, offset: (page.value - 1) * pageSize.value, search: String(route.query.search || ''),
  ...(visibility.value !== 'visible' ? { visibility: visibility.value } : {}),
  ...(projectId.value ? { project_id: projectId.value } : {}), ...(agentId.value ? { agent_id: agentId.value } : {}),
  statuses: statuses.value, sort_by: sortBy.value, sort_order: sortOrder.value, summary: true }))
let alive = true, generation = 0, timer = null, searchTimer = null
const loadTasks = async (quiet = false) => {
  if (timer !== null) window.clearTimeout(timer)
  const current = ++generation
  if (!quiet) loading.value = true
  failed.value = false
  try {
    const [response, projectResponse] = await Promise.all([taskAgentAPI('list', request.value),
      projectId.value && project.value?.project_id !== projectId.value ? taskAgentAPI('project', { project_id: projectId.value }) : null])
    if (!alive || current !== generation) return
    if (response.status !== 200 || !Number.isInteger(response.data?.total)) throw new Error()
    tasks.value = response.data.tasks; total.value = response.data.total; agents.value = response.data.agents || []
    if (projectResponse?.status === 200) project.value = projectResponse.data
    failed.value = Boolean(response.data.sync_error)
    selected.value = selected.value.filter(id => tasks.value.some(task => task.tid === id))
    const lastPage = Math.max(1, Math.ceil(total.value / pageSize.value))
    if (page.value > lastPage) updateQuery({ page: String(lastPage) })
  } catch { if (alive && current === generation) failed.value = true }
  finally {
    if (alive && current === generation) {
      loading.value = false
      if (failed.value || tasks.value.some(task => taskNeedsPolling(task.status))) timer = window.setTimeout(() => loadTasks(true), 5000)
    }
  }
}
watch(search, value => {
  clearTimeout(searchTimer)
  if (value === String(route.query.search || '')) return
  searchTimer = setTimeout(() => updateQuery({ search: value.trim() || undefined, page: undefined }), 200)
})
watch(() => route.query.search, value => { clearTimeout(searchTimer); search.value = String(value || '') })
watch(projectId, () => { project.value = null })
watch(projectDeletion, deleted => {
  if (!deleted) return
  saveFavorites(favorites.value.filter(id => !deleted.task_ids.includes(id)))
  loadTasks()
})
watch(() => JSON.stringify(request.value), () => { tasks.value = []; total.value = 0; selected.value = []; loadTasks() }, { immediate: true })
onBeforeUnmount(() => { alive = false; generation++; clearTimeout(searchTimer); if (timer !== null) window.clearTimeout(timer) })
</script>

<template>
  <main class="tasks-page">
    <header class="tasks-header">
      <div class="header-title"><h1>{{ t('workspace.taskAgentSpace.tasks') }}</h1><span aria-live="polite">{{ total }}</span><router-link v-if="projectId" class="project-scope" :to="{ name: 'taskAgentProject', params: { projectId } }">{{ project?.name || t('workspace.taskAgentSpace.projects') }}</router-link></div>
      <router-link :to="createRoute"><IconButton type="primary" class="create-task-button" :text="t('workspace.taskAgentSpace.create_new_task')"><template #icon><Plus /></template></IconButton></router-link>
    </header>
    <section class="tasks-toolbar" :aria-label="t('workspace.taskAgentSpace.task_list_controls')">
      <a-select :value="visibility" :aria-label="t('workspace.taskAgentSpace.task_visibility')" style="min-width: 120px" :options="['visible', 'hidden', 'all'].map(value => ({ value, label: t('workspace.taskAgentSpace.visibility_' + value) }))" @change="updateQuery({ visibility: $event === 'visible' ? undefined : $event, page: undefined })" />
      <a-input v-model:value="search" allow-clear :maxlength="256" class="task-search" :placeholder="t('workspace.taskAgentSpace.search_tasks')" :aria-label="t('workspace.taskAgentSpace.search_tasks')"><template #prefix><Search /></template></a-input>
      <div class="agent-filter-control"><AgentPicker class="agent-filter" :model-value="agentId || ''" :agents="agents" compact allow-clear :placeholder="t('workspace.taskAgentSpace.select_agent_filter')" @change="value => updateQuery({ agent_id: value || undefined, page: undefined })" /></div>
      <span class="toolbar-spacer" />
      <IconButton class="filter-button" :class="{ active: filterOpen || statuses.length }" :aria-expanded="filterOpen" aria-controls="task-status-filters" @click="filterOpen = !filterOpen" :text="t('workspace.taskAgentSpace.profile_filter') + (statuses.length ? ' (' + statuses.length + ')' : '')"><template #icon><Control /></template></IconButton>
      <div class="view-toggle" role="group" :aria-label="t('workspace.taskAgentSpace.task_view')"><IconButton v-for="item in ['list', 'card']" :key="item" type="text" :class="{ selected: view === item }" :aria-pressed="view === item" :aria-label="t(item === 'list' ? 'common.table_view' : 'common.card_view')" @click="changeView(item)" :text="t(item === 'list' ? 'common.table_view' : 'common.card_view')"><template #icon><ListOne v-if="item === 'list'" /><ViewGridCard v-else /></template></IconButton></div>
    </section>
    <section v-if="filterOpen" id="task-status-filters" class="filter-strip"><span>{{ t('common.status') }}</span><a-checkbox-group :value="statuses" :options="statusValues.map(value => ({ value, label: t('workspace.taskAgentSpace.status_' + value) }))" @change="value => updateQuery({ status: value.join(',') || undefined, page: undefined })" /><IconButton v-if="filtered" @click="clearFilters" :text="t('workspace.taskAgentSpace.profile_clear_filters')"><template #icon><Close /></template></IconButton></section>
    <section class="tasks-content" :aria-busy="loading">
      <a-alert v-if="failed" class="sync-notice" type="warning" show-icon :message="t('workspace.taskAgentSpace.sync_error')"><template #action><IconButton size="small" :loading="loading" @click="loadTasks()" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
      <div v-if="view === 'list'" class="table-container">
        <a-table class="tasks-table" row-key="tid" size="middle" :columns="columns" :data-source="tasks" :loading="loading" :pagination="pagination" :scroll="{ x: 1180 }" :custom-row="task => ({ onClick: event => openTask(task, event) })" :row-selection="{ selectedRowKeys: selected, onChange: value => selected = value, columnWidth: 32 }" @change="tableChange">
          <template #bodyCell="{ column, record }">
            <router-link v-if="column.key === 'title'" class="task-link" :title="record.title" :to="taskRoute(record)"><Star v-if="isFavorite(record)" class="favorite-icon" theme="filled" /><span>{{ record.title }}</span></router-link>
            <router-link v-else-if="column.key === 'agent'" class="agent-link" :title="agentName(profileOf(record))" :to="{ name: 'taskAgentEdit', params: { agentId: profileOf(record)?.agent_id || 'general' } }">{{ agentName(profileOf(record)) }}</router-link>
            <a-tag v-else-if="column.key === 'status'" :color="statusColor(record.status)" :bordered="false">{{ t('workspace.taskAgentSpace.status_' + record.status) }}</a-tag>
            <router-link v-else-if="column.key === 'project' && record.project_id" class="project-link" :to="{ name: 'taskAgentProject', params: { projectId: record.project_id } }" :title="projectName(record)">{{ projectName(record) }}</router-link>
            <span v-else-if="column.key === 'project'" class="secondary-text">{{ projectName(record) }}</span>
            <time v-else-if="column.key === 'created_at' || column.key === 'updated_at'" :datetime="record[column.key]">{{ dateLabel(record[column.key]) }}</time>
            <div v-else-if="column.key === 'action'" class="row-actions"><IconButton size="small" type="text" :disabled="Boolean(changingVisibility)" :loading="changingVisibility === record.tid" :aria-label="t('workspace.taskAgentSpace.' + (record.hidden ? 'restore_task' : 'hide_task'))" @click="toggleHidden(record)" :text="t('workspace.taskAgentSpace.' + (record.hidden ? 'restore_task' : 'hide_task'))"><template #icon><PreviewOpen v-if="record.hidden" /><PreviewCloseOne v-else /></template></IconButton><IconButton size="small" type="text" :aria-label="t('workspace.taskAgentSpace.' + (isFavorite(record) ? 'unfavorite_task' : 'favorite_task'))" :aria-pressed="isFavorite(record)" @click="toggleFavorite(record)" :text="t('workspace.taskAgentSpace.' + (isFavorite(record) ? 'unfavorite_task' : 'favorite_task'))"><template #icon><Star :theme="isFavorite(record) ? 'filled' : 'outline'" :class="{ 'favorite-icon': isFavorite(record) }" /></template></IconButton><a-tooltip :title="t('workspace.taskAgentSpace.task_detail')"><router-link :to="taskRoute(record)" :aria-label="t('workspace.taskAgentSpace.task_detail')"><PreviewOpen /></router-link></a-tooltip><IconButton size="small" type="text" danger :aria-label="t('workspace.taskAgentSpace.delete_task')" @click="askDelete(record)" :text="t('workspace.taskAgentSpace.delete_task')"><template #icon><Delete /></template></IconButton></div>
          </template>
          <template #emptyText><a-empty :description="t(filtered ? 'workspace.taskAgentSpace.no_matching_tasks' : 'workspace.taskAgentSpace.no_recent_activity')"><IconButton v-if="filtered" @click="clearFilters" :text="t('workspace.taskAgentSpace.profile_clear_filters')"><template #icon><Close /></template></IconButton></a-empty></template>
          <template #footer><div v-if="selected.length" class="selection-actions"><span>{{ t('workspace.taskAgentSpace.selected_tasks', { count: selected.length }) }}</span><IconButton size="small" @click="favoriteSelected" :text="t('workspace.taskAgentSpace.favorite_selected')"><template #icon><Star /></template></IconButton><IconButton size="small" type="text" @click="selected = []" :text="t('common.cancel')"><template #icon><Close /></template></IconButton></div></template>
        </a-table>
      </div>
      <a-spin v-else :spinning="loading">
        <div v-if="tasks.length" class="task-card-grid"><article v-for="task in tasks" :key="task.tid" class="task-card" @click="openTask(task, $event)"><div class="card-heading"><router-link class="task-link" :to="taskRoute(task)"><Star v-if="isFavorite(task)" class="favorite-icon" theme="filled" /><h2>{{ task.title }}</h2></router-link><a-tag :color="statusColor(task.status)" :bordered="false">{{ t('workspace.taskAgentSpace.status_' + task.status) }}</a-tag></div><p class="task-goal">{{ task.goal }}</p><dl><div><dt>{{ t('workspace.taskAgentSpace.source_agent') }}</dt><dd>{{ agentName(profileOf(task)) }}</dd></div><div><dt>{{ t('workspace.taskAgentSpace.projects') }}</dt><dd>{{ projectName(task) }}</dd></div><div><dt>{{ t('workspace.taskAgentSpace.current_cycle') }}</dt><dd>{{ task.current_cycle_index }}</dd></div></dl><footer><time :datetime="task.created_at">{{ dateLabel(task.created_at) }}</time><span class="card-actions"><IconButton size="small" type="text" :disabled="Boolean(changingVisibility)" :loading="changingVisibility === task.tid" :aria-label="t('workspace.taskAgentSpace.' + (task.hidden ? 'restore_task' : 'hide_task'))" @click="toggleHidden(task)" :text="t('workspace.taskAgentSpace.' + (task.hidden ? 'restore_task' : 'hide_task'))"><template #icon><PreviewOpen v-if="task.hidden" /><PreviewCloseOne v-else /></template></IconButton><IconButton size="small" type="text" danger :aria-label="t('workspace.taskAgentSpace.delete_task')" @click="askDelete(task)" :text="t('workspace.taskAgentSpace.delete_task')"><template #icon><Delete /></template></IconButton><IconButton size="small" type="text" :aria-label="t('workspace.taskAgentSpace.' + (isFavorite(task) ? 'unfavorite_task' : 'favorite_task'))" :aria-pressed="isFavorite(task)" @click="toggleFavorite(task)" :text="t('workspace.taskAgentSpace.' + (isFavorite(task) ? 'unfavorite_task' : 'favorite_task'))"><template #icon><Star :theme="isFavorite(task) ? 'filled' : 'outline'" :class="{ 'favorite-icon': isFavorite(task) }" /></template></IconButton></span></footer></article></div>
        <a-empty v-else class="card-empty" :description="t(filtered ? 'workspace.taskAgentSpace.no_matching_tasks' : 'workspace.taskAgentSpace.no_recent_activity')" />
        <a-pagination v-if="total" class="card-pagination" v-bind="pagination" @change="(current, size) => updateQuery({ page: String(current), page_size: String(size) })" />
      </a-spin>
    </section>
    <a-modal :open="!!pendingDelete" :title="t('workspace.taskAgentSpace.delete_task')" :ok-text="t('common.delete')" :cancel-text="t('common.cancel')" :ok-button-props="{ danger: true }" :confirm-loading="deleting" :cancel-button-props="{ disabled: deleting }" :closable="!deleting" :keyboard="!deleting" :mask-closable="false" @ok="confirmDelete" @cancel="!deleting && (pendingDelete = null)">
      <p>{{ t('workspace.taskAgentSpace.delete_task_confirm', { title: pendingDelete?.title || '' }) }}</p>
      <a-alert v-if="deleteError" type="error" show-icon :message="t('workspace.taskAgentSpace.delete_error_' + deleteError)" />
    </a-modal>
  </main>
</template>

<style scoped>
.tasks-page { display: flex; flex-direction: column; height: 100%; min-width: 0; color: var(--site-text-color); }
.tasks-header { display: flex; flex-shrink: 0; min-height: 56px; padding: 0 8px; align-items: center; justify-content: space-between; gap: 12px; border-bottom: var(--light-border); background: var(--component-background); }
.header-title { display: flex; min-width: 0; align-items: baseline; gap: 9px; }
.header-title h1 { margin: 0; font-size: 18px; font-weight: 650; }
.header-title > span { color: var(--site-secondary-text-color); font-size: 12px; font-variant-numeric: tabular-nums; }
:deep(.create-task-button) { display: inline-flex; align-items: center; gap: 6px; border-radius: 6px; }
.project-scope { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: var(--site-secondary-text-color); }
.tasks-toolbar { display: flex; flex-shrink: 0; min-height: 56px; padding: 10px 8px; align-items: center; gap: 8px; border-bottom: var(--light-border); background: var(--component-background); }
.task-search { width: min(250px, 36vw); min-width: 180px; }
.agent-filter-control { position: relative; width: 220px; min-width: 160px; }
.agent-filter { width: 100%; }
.toolbar-spacer { flex: 1; }
:deep(.filter-button) { display: inline-flex; align-items: center; gap: 6px; color: var(--site-secondary-text-color); }
:deep(.filter-button).active { color: var(--site-text-color); border-color: var(--color-primary); }
.filter-count { margin-left: 6px; color: var(--color-primary); font-variant-numeric: tabular-nums; }
.view-toggle { display: flex; flex-shrink: 0; gap: 2px; padding: 2px; border: var(--light-border); border-radius: 6px; }
.view-toggle :deep(.ant-btn) { width: 30px; height: 28px; padding: 0; color: var(--site-secondary-text-color); }
.view-toggle :deep(.selected) { background: var(--gray-background); color: var(--site-text-color); }
.filter-strip { display: flex; flex-shrink: 0; align-items: center; flex-wrap: wrap; gap: 12px; padding: 8px; border-bottom: var(--light-border); font-size: 12px; }
.filter-strip :deep(.ant-checkbox-group) { display: flex; flex-wrap: wrap; gap: 8px 12px; }
.filter-strip :deep(.ant-checkbox-wrapper) { margin: 0; font-size: 12px; }
.tasks-content { flex: 1; min-width: 0; min-height: 0; overflow: auto; padding: 20px 8px 12px; background: var(--gray-background); }
.sync-notice { margin-bottom: 12px; }
.table-container { overflow: hidden; border: var(--light-border); border-radius: 8px; background: var(--component-background); }
.tasks-table :deep(.ant-table) { background: transparent; }
.tasks-table :deep(.ant-table-thead > tr > th) { height: 46px; background: var(--gray-background); color: var(--site-secondary-text-color); font-size: 12px; font-weight: 500; }
.tasks-table :deep(.ant-table-tbody > tr > td) { height: 55px; background: var(--component-background); color: var(--site-text-color); font-size: 13px; }
.tasks-table :deep(.ant-table-tbody > tr:hover > td) { background: var(--more-hover-background); }
.tasks-table :deep(.ant-table-footer) { min-height: 24px; padding: 0 16px; background: var(--gray-background); }
.tasks-table :deep(.ant-pagination) { margin: 16px; }
.task-link, .agent-link, .project-link { max-width: 100%; color: var(--site-text-color); }
.task-link { display: inline-flex; align-items: center; gap: 6px; }
.task-link span, .agent-link, .project-link { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agent-link, .project-link { display: block; }
.task-link:hover, .agent-link:hover, .project-link:hover { color: var(--color-primary); }
.favorite-icon { flex-shrink: 0; color: #d99c16; }
.secondary-text, time { color: var(--site-secondary-text-color); font-size: 12px; }
time { white-space: nowrap; font-variant-numeric: tabular-nums; }
.tasks-table time { color: var(--site-text-color); font-size: 13px; }
.row-actions { display: flex; align-items: center; justify-content: center; gap: 4px; }
.row-actions :deep(.ant-btn), .row-actions a { display: grid; place-items: center; width: 28px; height: 28px; padding: 0; border-radius: 5px; color: var(--site-secondary-text-color); }
.row-actions :deep(.ant-btn-dangerous) { color: var(--error-color, #ff4d4f); }
.card-actions { display: inline-flex; gap: 4px; }
.row-actions a:hover { color: var(--color-primary); background: var(--more-hover-background); }
.row-actions a:focus-visible { outline: 2px solid var(--color-primary); }
.selection-actions { display: flex; justify-content: flex-end; align-items: center; gap: 8px; padding: 8px 0; font-size: 12px; }
.task-card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.tasks-table :deep(.ant-table-row), .task-card { cursor: pointer; }
.task-card { min-width: 0; padding: 20px; border: var(--light-border); border-radius: 8px; background: var(--component-background); }
.card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.card-heading .task-link { min-width: 0; }
.card-heading h2 { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; margin: 0; font-size: 15px; font-weight: 600; }
.card-heading :deep(.ant-tag) { flex-shrink: 0; margin: 0; }
.task-goal { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; min-height: 40px; overflow: hidden; margin: 14px 0; color: var(--site-secondary-text-color); font-size: 13px; }
.task-card dl { display: grid; gap: 8px; margin: 0; font-size: 12px; }
.task-card dl > div { display: flex; gap: 12px; }
.task-card dt { flex-shrink: 0; color: var(--site-secondary-text-color); }
.task-card dd { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin: 0; }
.task-card footer { display: flex; align-items: center; justify-content: space-between; margin-top: 14px; padding-top: 10px; border-top: var(--light-border); }
.card-pagination { display: flex; justify-content: flex-end; margin-top: 20px; }
.card-empty { padding: 48px 0; }
@media (hover: hover) and (pointer: fine) { .row-actions { opacity: 0; } .tasks-table :deep(.ant-table-row:hover) .row-actions, .row-actions:focus-within { opacity: 1; } }
@media (max-width: 1280px) { .task-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 900px) { .tasks-toolbar { flex-wrap: wrap; }.tasks-content { padding: 16px; }.task-search { flex: 1; min-width: 160px; }.agent-filter-control { flex: 1; }.toolbar-spacer { display: none; }.task-card-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
