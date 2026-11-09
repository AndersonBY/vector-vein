<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme } from 'ant-design-vue'
import { FolderOpen, CheckOne, LoadingFour, Refresh } from '@/icons'
import { taskAgentAPI } from '@/api/taskAgent'
const props = defineProps({ modelValue: { type: String, default: '' }, project: Object, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const { token } = theme.useToken()
const open = ref(false), projects = ref([]), loading = ref(false), failed = ref(false)
const label = computed(() => props.modelValue ? (props.project?.name || projects.value.find(project => project.project_id === props.modelValue)?.name || t('workspace.taskAgentSpace.select_project')) : t('workspace.taskAgentSpace.select_project'))
let alive = true, generation = 0
const load = async () => {
  const request = ++generation
  loading.value = true; failed.value = false
  try {
    const response = await taskAgentAPI('projects')
    if (!alive || request !== generation) return
    if (response.status !== 200) throw new Error()
    projects.value = response.data.projects
  } catch { if (alive && request === generation) failed.value = true }
  finally { if (alive && request === generation) loading.value = false }
}
const select = ({ key }) => {
  if (props.disabled) return
  if (key === 'retry') { load(); return }
  if (key !== 'standalone' && !projects.value.some(project => 'project:' + project.project_id === key)) return
  emit('update:modelValue', key === 'standalone' ? '' : key.slice('project:'.length))
  open.value = false
}
onMounted(load)
onBeforeUnmount(() => { alive = false; generation++ })
</script>
<template>
  <div class="project-picker">
    <a-dropdown :open="open" :trigger="['click']" :disabled="disabled" placement="bottomLeft" @open-change="open = $event; if ($event) load()">
      <button type="button" class="project-context-tab" :disabled="disabled" :title="label" :aria-label="t('workspace.taskAgentSpace.select_project')" :aria-expanded="open" aria-haspopup="menu"><FolderOpen /><span>{{ label }}</span></button>
      <template #overlay>
        <a-menu class="project-picker-menu" :style="{ '--project-picker-secondary': token.colorTextSecondary }" :selected-keys="[modelValue ? 'project:' + modelValue : 'standalone']" @click="select">
          <a-menu-item key="standalone" :disabled="disabled"><div class="project-option"><div><strong>{{ t('workspace.taskAgentSpace.no_project') }}</strong><small>{{ t('workspace.taskAgentSpace.standalone_task') }}</small></div><CheckOne v-if="!modelValue" :size="14" /></div></a-menu-item>
          <a-menu-divider />
          <a-menu-item v-for="item in projects" :key="'project:' + item.project_id" :disabled="disabled"><div class="project-option"><FolderOpen /><div><strong>{{ item.name }}</strong><small>{{ t('workspace.taskAgentSpace.task_count', { count: item.task_count }) }}</small></div><CheckOne v-if="modelValue === item.project_id" :size="14" /></div></a-menu-item>
          <a-menu-item v-if="failed" key="retry"><div class="project-option"><Refresh /><span>{{ t('workspace.taskAgentSpace.project_load_failed') }} · {{ t('workspace.taskAgentSpace.retry') }}</span></div></a-menu-item>
          <a-menu-item v-else-if="loading && !projects.length" key="loading" disabled><LoadingFour spin /> {{ t('workspace.taskAgentSpace.loading_projects') }}</a-menu-item>
          <a-menu-item v-else-if="!projects.length" key="empty" disabled>{{ t('workspace.taskAgentSpace.no_sidebar_projects') }}</a-menu-item>
        </a-menu>
      </template>
    </a-dropdown>
  </div>
</template>
<style scoped>
.project-picker { display: flex; max-width: 260px; min-width: 0; }
.project-context-tab { display: flex; align-items: center; gap: 8px; min-width: 0; min-height: 38px; padding: 0 12px; border: var(--border-color); border-bottom: 0; border-radius: 8px 8px 0 0; background: var(--component-background); color: var(--site-text-color); font: inherit; font-size: 13px; cursor: pointer; }
.project-context-tab span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.project-context-tab svg { flex-shrink: 0; }
.project-context-tab:disabled { opacity: .5; cursor: default; }.project-context-tab:focus-visible { outline: 2px solid var(--color-primary); outline-offset: -2px; }
.project-context-tab:hover:not(:disabled) { background: var(--more-hover-background); }
.project-picker-menu { width: 320px; max-width: calc(100vw - 32px); max-height: min(440px, 60vh); overflow-y: auto; }
.project-option { display: flex; align-items: center; gap: 10px; padding: 5px 0; }.project-option > div { flex: 1; min-width: 0; }.project-option > svg { flex-shrink: 0; }
.project-option strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 500; }.project-option small { display: block; margin-top: 3px; color: var(--project-picker-secondary); font-size: 11px; }
</style>
