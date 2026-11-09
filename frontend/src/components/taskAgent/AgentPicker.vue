<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Robot, Right, CheckOne, Close, Refresh } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
import PickerModal from './PickerModal.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  agents: { type: Array, default: null },
  disabled: Boolean,
  compact: Boolean,
  allowClear: Boolean,
  placeholder: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'change'])
const { t } = useI18n()
const tr = (key, params) => t(`workspace.taskAgentSpace.picker.${key}`, params)
const open = ref(false), loading = ref(false), failed = ref(false)
const knownAgents = ref([]), selectedAgent = ref(null)
const search = ref(''), filter = ref('all'), page = ref(1), draftId = ref('')
const pageSize = 10
let alive = true, generation = 0, selectedGeneration = 0
const nameOf = agent => agent?.name || (agent?.agent_id === 'general' ? t('workspace.taskAgentSpace.general_agent') : agent?.agent_id || '')
const descriptionOf = agent => agent?.description || t(`workspace.taskAgentSpace.${agent?.agent_id === 'general' ? 'general_description' : 'profile_no_description'}`)
const available = computed(() => props.agents ?? knownAgents.value)
const current = computed(() => available.value.find(agent => agent.agent_id === props.modelValue) ||
  (selectedAgent.value?.agent_id === props.modelValue ? selectedAgent.value : null))
const label = computed(() => props.modelValue ? nameOf(current.value) || props.modelValue : props.placeholder || tr('select_agent'))
const filters = computed(() => ['all', 'shell', 'sub_agents', 'workflows', 'skills', 'mcp'].map(value => ({
  value, label: t(`workspace.taskAgentSpace.profile_filter_${value}`),
})))
const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return available.value.filter(agent => (!query || `${nameOf(agent)} ${descriptionOf(agent)} ${agent.model || ''}`.toLocaleLowerCase().includes(query)) &&
    (filter.value === 'all' || (filter.value === 'shell' && agent.allow_shell) ||
      (filter.value === 'sub_agents' && agent.allow_sub_agents) ||
      (filter.value === 'workflows' && agent.workflow_ids?.length) ||
      (filter.value === 'skills' && agent.skill_ids?.length) ||
      (filter.value === 'mcp' && agent.mcp_tool_ids?.length)))
})
const currentPage = computed(() => Math.min(page.value, Math.max(1, Math.ceil(filtered.value.length / pageSize))))
const visible = computed(() => filtered.value.slice((currentPage.value - 1) * pageSize, currentPage.value * pageSize))
const draft = computed(() => available.value.find(agent => agent.agent_id === draftId.value))
const preview = computed(() => draft.value || visible.value[0])
const load = async () => {
  const request = ++generation
  loading.value = true; failed.value = false
  try {
    const response = await taskAgentAPI('profiles')
    if (!alive || request !== generation || !open.value) return
    if (response.status !== 200 || !Array.isArray(response.data?.agents)) throw new Error()
    knownAgents.value = response.data.agents
  } catch { if (alive && request === generation) failed.value = true }
  finally { if (alive && request === generation) loading.value = false }
}
const show = () => {
  if (props.disabled) return
  draftId.value = props.modelValue; search.value = ''; filter.value = 'all'; page.value = 1
  failed.value = false; open.value = true
  if (props.agents === null) load()
}
const close = () => { open.value = false; generation++; loading.value = false }
const confirm = () => {
  if (props.disabled || loading.value || failed.value || !draft.value) return
  selectedAgent.value = draft.value
  emit('update:modelValue', draft.value.agent_id)
  emit('change', draft.value.agent_id, draft.value)
  close()
}
const clear = () => {
  if (props.disabled) return
  emit('update:modelValue', '')
  emit('change', '', null)
}
watch([search, filter], () => { page.value = 1 })
watch(() => props.disabled, value => { if (value) close() })
watch([() => props.modelValue, available], async ([id]) => {
  const request = ++selectedGeneration
  if (!id || current.value || props.agents !== null) return
  try {
    const response = await taskAgentAPI('profile', { agent_id: id })
    if (alive && request === selectedGeneration && props.modelValue === id && response.status === 200 && response.data?.agent_id === id) selectedAgent.value = response.data
  } catch { /* The modal provides a retryable catalog if the label cannot be loaded. */ }
}, { immediate: true })
onBeforeUnmount(() => { alive = false; generation++; selectedGeneration++ })
</script>

<template>
  <div class="task-agent-picker" :class="{ compact }">
    <a-button class="task-agent-picker-trigger" :disabled="disabled" aria-haspopup="dialog" :aria-expanded="open" :aria-label="placeholder || tr('select_agent')" :title="label" @click="show">
      <Robot aria-hidden="true" />
      <span class="picker-trigger-copy"><span class="picker-trigger-title">{{ label }}</span><span class="picker-trigger-subtitle">{{ current ? descriptionOf(current) : tr('agent_hint') }}</span></span>
      <Right class="picker-chevron" aria-hidden="true" />
    </a-button>
    <IconButton v-if="allowClear && modelValue" class="picker-clear" type="text" size="small" :disabled="disabled" @click="clear" :text="tr('clear')"><template #icon><Close /></template></IconButton>
    <PickerModal :open="open" :title="tr('select_agent')" :confirm-disabled="disabled || loading || failed || !draft" @confirm="confirm" @cancel="close">
      <template #toolbar>
        <a-input v-model:value="search" class="picker-search" allow-clear :placeholder="tr('search_agents')" :aria-label="tr('search_agents')" />
        <a-select v-model:value="filter" class="picker-filter" :options="filters" :aria-label="tr('agent_capabilities')" />
        <span class="picker-result-count" aria-live="polite">{{ tr('results', { count: filtered.length }) }}</span>
      </template>
      <template #list>
        <div v-if="failed" class="picker-panel-state" role="alert"><span>{{ tr('agents_failed') }}</span><IconButton @click="load" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton></div>
        <div v-else-if="loading" class="picker-panel-state" :aria-label="tr('loading')" aria-busy="true"><a-spin /></div>
        <a-empty v-else-if="!visible.length" class="picker-panel-state" :description="tr('no_agents')" />
        <template v-else>
          <div class="picker-rows">
            <button v-for="agent in visible" :key="agent.agent_id" type="button" class="picker-row" :class="{ 'is-selected': draftId === agent.agent_id }" :aria-pressed="draftId === agent.agent_id" @click="draftId = agent.agent_id">
              <Robot aria-hidden="true" />
              <span class="picker-row-copy"><span class="picker-row-title">{{ nameOf(agent) }}</span><span class="picker-row-meta">{{ agent.model || t('workspace.taskAgentSpace.profile_follow_model') }}</span><span class="picker-row-description">{{ descriptionOf(agent) }}</span></span>
              <span class="picker-row-check"><CheckOne v-if="draftId === agent.agent_id" aria-hidden="true" /></span>
            </button>
          </div>
          <a-pagination v-if="filtered.length > pageSize" class="picker-pagination" :current="currentPage" :page-size="pageSize" :total="filtered.length" :show-size-changer="false" size="small" @change="page = $event" />
        </template>
      </template>
      <template #detail>
        <template v-if="preview && !loading && !failed">
          <h3>{{ nameOf(preview) }}</h3><p>{{ descriptionOf(preview) }}</p>
          <dl>
            <dt>{{ tr('model') }}</dt><dd>{{ preview.model || t('workspace.taskAgentSpace.profile_follow_model') }}</dd>
            <dt>Bash</dt><dd>{{ tr(preview.allow_shell ? 'enabled' : 'disabled') }}</dd>
            <dt>{{ t('workspace.taskAgentSpace.sub_agent') }}</dt><dd>{{ tr(preview.allow_sub_agents ? 'enabled' : 'disabled') }}</dd>
            <dt>{{ tr('extensions') }}</dt><dd>{{ tr('extension_counts', { workflows: preview.workflow_ids?.length || 0, skills: preview.skill_ids?.length || 0, mcp: preview.mcp_tool_ids?.length || 0 }) }}</dd>
          </dl>
          <template v-if="preview.instructions"><h4>{{ tr('instructions') }}</h4><pre class="picker-instructions">{{ preview.instructions }}</pre></template>
        </template>
        <div v-else class="picker-panel-state picker-detail-empty">{{ tr('agent_preview') }}</div>
      </template>
    </PickerModal>
  </div>
</template>
