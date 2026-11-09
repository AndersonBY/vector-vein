<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ListOne, Right, CheckOne, Close, Refresh } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import { formatTaskTime } from '@/utils/taskAgentPresentation'
import PickerModal from './PickerModal.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  // A caller that already loads task details can supply its result here.
  selectedTask: { type: Object, default: undefined },
  disabled: Boolean,
  compact: Boolean,
  allowClear: Boolean,
  placeholder: { type: String, default: '' },
  visibility: { type: String, default: 'all' },
})
const emit = defineEmits(['update:modelValue', 'change'])
const { t, locale } = useI18n()
const tr = (key, params) => t(`workspace.taskAgentSpace.picker.${key}`, params)
const open = ref(false), loading = ref(false), failed = ref(false), syncError = ref(false)
const tasks = ref([]), agents = ref([]), projects = ref([]), total = ref(0)
const filtersFailed = ref(false), filtersLoading = ref(false)
const knownTask = ref(null), draft = ref(null)
const search = ref(''), agentId = ref(''), projectId = ref(''), status = ref(''), visibilityFilter = ref('all'), page = ref(1)
const pageSize = 20
let alive = true, generation = 0, selectedGeneration = 0, filterGeneration = 0, timer = null
const current = computed(() => props.selectedTask?.tid === props.modelValue ? props.selectedTask :
  knownTask.value?.tid === props.modelValue ? knownTask.value : null)
const titleOf = task => task?.title || task?.goal || task?.tid || ''
const agentName = agent => agent?.name || (agent?.agent_id && agent.agent_id !== 'general' ? agent.agent_id : t('workspace.taskAgentSpace.general_agent'))
const projectName = task => task?.config_snapshot?.project?.name || projects.value.find(project => project.project_id === task?.project_id)?.name || t('workspace.taskAgentSpace.task_without_project')
const label = computed(() => props.modelValue ? titleOf(current.value) || props.modelValue : props.placeholder || tr('select_task'))
const preview = computed(() => draft.value || tasks.value[0])
const statusValues = ['PENDING', 'PROCESSING', 'WAITING_FOR_USER', 'WAITING_FOR_APPROVAL', 'WAITING_FOR_WORKFLOW', 'COMPLETED', 'PAUSED', 'FAILED', 'INTERRUPTED']
const statusOptions = computed(() => [{ value: '', label: tr('all_statuses') },
  ...statusValues.map(value => ({ value, label: t(`workspace.taskAgentSpace.status_${value}`) }))])
const agentOptions = computed(() => [{ value: '', label: tr('all_agents') }, ...agents.value.map(agent => ({ value: agent.agent_id, label: agentName(agent) }))])
const projectOptions = computed(() => [{ value: '', label: tr('all_projects') }, ...projects.value.map(project => ({ value: project.project_id, label: project.name }))])
const visibilityOptions = computed(() => ['all', 'visible', 'hidden'].map(value => ({ value, label: tr(`visibility_${value}`) })))

const load = async () => {
  const request = ++generation
  loading.value = true; failed.value = false; syncError.value = false
  try {
    const response = await taskAgentAPI('list', {
      limit: pageSize, offset: (page.value - 1) * pageSize, search: search.value.trim(),
      ...(agentId.value ? { agent_id: agentId.value } : {}),
      ...(projectId.value ? { project_id: projectId.value } : {}),
      ...(status.value ? { statuses: [status.value] } : {}),
      visibility: visibilityFilter.value, summary: true, sort_by: 'updated_at', sort_order: 'desc',
    })
    if (!alive || request !== generation || !open.value) return
    if (response.status !== 200 || !Array.isArray(response.data?.tasks)) throw new Error()
    total.value = response.data.total || 0
    const lastPage = Math.max(1, Math.ceil(total.value / pageSize))
    if (page.value > lastPage) { page.value = lastPage; return }
    tasks.value = response.data.tasks
    syncError.value = Boolean(response.data.sync_error)
  } catch { if (alive && request === generation) { tasks.value = []; failed.value = true } }
  finally { if (alive && request === generation) loading.value = false }
}
const queueLoad = (delay = 0) => {
  clearTimeout(timer); generation++
  if (!open.value) return
  tasks.value = []; loading.value = true
  timer = setTimeout(load, delay)
}
const loadFilters = async () => {
  const request = ++filterGeneration
  filtersLoading.value = true; filtersFailed.value = false
  const responses = await Promise.allSettled([taskAgentAPI('profiles'), taskAgentAPI('projects')])
  if (!alive || request !== filterGeneration || !open.value) return
  const values = responses.map(response => response.status === 'fulfilled' && response.value.status === 200 ? response.value.data : null)
  if (Array.isArray(values[0]?.agents)) agents.value = values[0].agents
  if (Array.isArray(values[1]?.projects)) projects.value = values[1].projects
  filtersFailed.value = !Array.isArray(values[0]?.agents) || !Array.isArray(values[1]?.projects)
  filtersLoading.value = false
}
const show = () => {
  if (props.disabled) return
  search.value = ''; agentId.value = ''; projectId.value = ''; status.value = ''
  visibilityFilter.value = ['visible', 'hidden', 'all'].includes(props.visibility) ? props.visibility : 'all'
  page.value = 1; draft.value = current.value
  open.value = true
  load(); loadFilters()
}
const close = () => {
  open.value = false; generation++; filterGeneration++
  clearTimeout(timer); loading.value = false; filtersLoading.value = false
}
const confirm = () => {
  if (props.disabled || loading.value || failed.value || !draft.value) return
  knownTask.value = draft.value
  emit('update:modelValue', draft.value.tid)
  emit('change', draft.value.tid, draft.value)
  close()
}
const clear = () => {
  if (props.disabled) return
  emit('update:modelValue', '')
  emit('change', '', null)
}
watch([search, agentId, projectId, status, visibilityFilter], (values, previous) => {
  page.value = 1
  queueLoad(values[0] !== previous[0] ? 200 : 0)
}, { flush: 'sync' })
watch(page, () => queueLoad(), { flush: 'sync' })
watch(current, value => { if (open.value && !draft.value && value) draft.value = value })
watch(() => props.disabled, value => { if (value) close() })
watch([() => props.modelValue, () => props.selectedTask], async ([id]) => {
  const request = ++selectedGeneration
  if (!id || props.selectedTask !== undefined || current.value) return
  try {
    const response = await taskAgentAPI('get', { task_id: id, cached: true })
    if (alive && request === selectedGeneration && props.modelValue === id && response.status === 200 && response.data?.task?.tid === id) knownTask.value = response.data.task
  } catch { /* The modal remains available if a saved selection no longer exists. */ }
}, { immediate: true })
onBeforeUnmount(() => { alive = false; generation++; selectedGeneration++; filterGeneration++; clearTimeout(timer) })
</script>

<template>
  <div class="task-agent-picker" :class="{ compact }">
    <a-button class="task-agent-picker-trigger" :disabled="disabled" aria-haspopup="dialog" :aria-expanded="open" :aria-label="placeholder || tr('select_task')" :title="label" @click="show">
      <ListOne aria-hidden="true" />
      <span class="picker-trigger-copy"><span class="picker-trigger-title">{{ label }}</span><span class="picker-trigger-subtitle">{{ current ? projectName(current) : tr('task_hint') }}</span></span>
      <Right class="picker-chevron" aria-hidden="true" />
    </a-button>
    <IconButton v-if="allowClear && modelValue" class="picker-clear" type="text" size="small" :disabled="disabled" @click="clear" :text="tr('clear')"><template #icon><Close /></template></IconButton>
    <PickerModal :open="open" :title="tr('select_task')" :confirm-disabled="disabled || loading || failed || !draft" @confirm="confirm" @cancel="close">
      <template #toolbar>
        <a-input v-model:value="search" class="picker-search" allow-clear :placeholder="tr('search_tasks')" :aria-label="tr('search_tasks')" />
        <div class="picker-filters">
          <a-select v-model:value="agentId" class="picker-filter" :options="agentOptions" :loading="filtersLoading" :aria-label="tr('all_agents')" />
          <a-select v-model:value="projectId" class="picker-filter" :options="projectOptions" :loading="filtersLoading" :aria-label="tr('all_projects')" />
          <a-select v-model:value="status" class="picker-filter" :options="statusOptions" :aria-label="tr('all_statuses')" />
          <a-select v-model:value="visibilityFilter" class="picker-filter" :options="visibilityOptions" :aria-label="tr('visibility')" />
          <span class="picker-result-count" aria-live="polite">{{ tr('results', { count: total }) }}</span>
        </div>
      </template>
      <template #list>
        <a-alert v-if="filtersFailed" type="warning" :message="tr('filters_failed')"><template #action><IconButton type="text" size="small" @click="loadFilters" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
        <a-alert v-if="syncError" type="warning" :message="t('workspace.taskAgentSpace.sync_error')"><template #action><IconButton type="text" size="small" @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></template></a-alert>
        <div v-if="failed" class="picker-panel-state" role="alert"><span>{{ tr('tasks_failed') }}</span><IconButton @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></div>
        <div v-else-if="loading" class="picker-panel-state" :aria-label="tr('loading')" aria-busy="true"><a-spin /></div>
        <a-empty v-else-if="!tasks.length" class="picker-panel-state" :description="tr('no_tasks')" />
        <template v-else>
          <div class="picker-rows">
            <button v-for="task in tasks" :key="task.tid" type="button" class="picker-row" :class="{ 'is-selected': draft?.tid === task.tid }" :aria-pressed="draft?.tid === task.tid" @click="draft = task">
              <span class="picker-row-copy"><span class="picker-row-title">{{ titleOf(task) }}</span>
                <span class="picker-row-meta"><span v-if="task.status">{{ t(`workspace.taskAgentSpace.status_${task.status}`) }}</span><span>{{ projectName(task) }}</span><span v-if="task.hidden">{{ tr('hidden') }}</span></span>
                <span class="picker-row-description">{{ task.goal }}</span>
                <span class="picker-row-meta"><span>{{ agentName(task.config_snapshot?.agent_profile) }}</span><time v-if="task.updated_at">{{ formatTaskTime(task.updated_at, locale) }}</time></span>
              </span>
              <span class="picker-row-check"><CheckOne v-if="draft?.tid === task.tid" aria-hidden="true" /></span>
            </button>
          </div>
          <a-pagination v-if="total > pageSize" class="picker-pagination" :current="page" :page-size="pageSize" :total="total" :show-size-changer="false" size="small" @change="page = $event" />
        </template>
      </template>
      <template #detail>
        <template v-if="preview && !loading && !failed">
          <h3>{{ titleOf(preview) }}</h3>
          <dl>
            <dt>{{ tr('agent') }}</dt><dd>{{ agentName(preview.config_snapshot?.agent_profile) }}</dd>
            <dt>{{ tr('project') }}</dt><dd>{{ projectName(preview) }}</dd>
            <dt>{{ tr('model') }}</dt><dd>{{ preview.model || '—' }}</dd>
            <dt v-if="preview.status">{{ tr('status') }}</dt><dd v-if="preview.status">{{ t(`workspace.taskAgentSpace.status_${preview.status}`) }}</dd>
            <dt v-if="preview.updated_at">{{ tr('updated') }}</dt><dd v-if="preview.updated_at">{{ formatTaskTime(preview.updated_at, locale) }}</dd>
          </dl>
          <h4>{{ tr('goal') }}</h4><p>{{ preview.goal }}</p>
        </template>
        <div v-else class="picker-panel-state picker-detail-empty">{{ tr('task_preview') }}</div>
      </template>
    </PickerModal>
  </div>
</template>
