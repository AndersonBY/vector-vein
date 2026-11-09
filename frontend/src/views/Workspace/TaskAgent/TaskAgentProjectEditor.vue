<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, inject, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme } from 'ant-design-vue'
import { v4 as uuidv4 } from 'uuid'
import { FolderOpen, Plus, Close, Star } from '@/icons'
import { PhLaptop } from '@phosphor-icons/vue'
import { taskAgentAPI } from '@/api/taskAgent'
const props = defineProps({ open: Boolean, project: Object })
const emit = defineEmits(['update:open', 'saved'])
const { t } = useI18n()
const { token } = theme.useToken()
const refreshProjects = inject('refreshTaskAgentProjects', null)
const name = ref(''), roots = ref([]), saving = ref(false), picking = ref(false), error = ref(''), requestId = ref('')
const folderName = path => path?.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || path || ''
const defaultName = computed(() => folderName(roots.value[0]))
watch(() => props.open, value => {
  if (!value) return
  name.value = props.project?.name || ''; roots.value = [...(props.project?.roots || [])]
  requestId.value = props.project?.project_id || uuidv4().replaceAll('-', ''); error.value = ''
}, { immediate: true })
const pickFolder = async () => {
  picking.value = true; error.value = ''
  try {
    const folder = await window.pywebview.api.open_folder_dialog(roots.value.at(-1) || '')
    if (folder && !roots.value.includes(folder)) roots.value.push(folder)
  } catch { error.value = 'project_pick_failed' }
  finally { picking.value = false }
}
const makePrimary = index => { const [root] = roots.value.splice(index, 1); roots.value.unshift(root) }
const save = async () => {
  if (saving.value || picking.value || !roots.value.length) return
  saving.value = true; error.value = ''
  try {
    const response = await taskAgentAPI('save_project', { project_id: requestId.value, name: name.value.trim(), roots: [...roots.value], ...(props.project ? { expected_updated_at: props.project.updated_at } : {}) })
    if (response.status !== 200) {
      error.value = response.status === 409 ? 'project_changed' : response.data?.project_error ? 'project_error_' + response.data.project_error : 'project_save_failed'
      return
    }
    emit('saved', response.data); emit('update:open', false); refreshProjects?.()
  } catch { error.value = 'project_save_failed' }
  finally { saving.value = false }
}
</script>
<template>
  <a-modal :open="open" :title="t(project ? 'workspace.taskAgentSpace.edit_project' : 'workspace.taskAgentSpace.create_project')" :width="560" :confirm-loading="saving" :ok-button-props="{ disabled: !roots.length || picking }" :cancel-button-props="{ disabled: saving }" :closable="!saving" :mask-closable="false" :ok-text="t(project ? 'workspace.taskAgentSpace.save_project' : 'workspace.taskAgentSpace.create_project')" @ok="save" @cancel="emit('update:open', false)">
    <a-form layout="vertical" class="project-form" :style="{ '--light-border': `1px solid ${token.colorBorderSecondary}`, '--more-hover-background': token.colorFillTertiary, '--color-primary': token.colorPrimary, '--site-secondary-text-color': token.colorTextSecondary }">
      <a-form-item><a-input v-model:value="name" :disabled="saving" :maxlength="160" :placeholder="defaultName || t('workspace.taskAgentSpace.project_name_optional')" :aria-label="t('workspace.taskAgentSpace.project_name')"><template #prefix><FolderOpen /></template></a-input></a-form-item>
      <a-form-item>
        <div class="project-folders-heading"><span>{{ t('workspace.taskAgentSpace.project_folders') }}</span><span class="project-folders-device"><PhLaptop aria-hidden="true" />{{ t('workspace.taskAgentSpace.this_computer') }}</span></div>
        <div class="project-folder-list">
          <div v-for="(root, index) in roots" :key="root" class="project-folder-row" tabindex="0" :aria-label="root">
              <FolderOpen class="project-folder-icon" aria-hidden="true" />
              <a-tooltip :title="root" :trigger="['hover', 'focus']" placement="bottom" :mouse-enter-delay="0.4" :overlay-style="{ maxWidth: 'min(640px, calc(100vw - 32px))' }" :overlay-inner-style="{ overflowWrap: 'anywhere' }"><strong tabindex="0">{{ folderName(root) }}</strong></a-tooltip>
              <small v-if="index === 0" class="project-primary-badge">{{ t('workspace.taskAgentSpace.primary_folder') }}</small>
              <IconButton v-else class="project-folder-action" type="text" size="small" :disabled="saving" @click="makePrimary(index)" :text="t('workspace.taskAgentSpace.make_primary')"><template #icon><Star /></template></IconButton>
              <IconButton class="project-folder-action" type="text" size="small" :disabled="saving" :aria-label="t('workspace.taskAgentSpace.remove_folder', { name: folderName(root) })" @click="roots.splice(index, 1)" :text="t('workspace.taskAgentSpace.remove_folder', { name: folderName(root) })"><template #icon><Close /></template></IconButton>
            </div>
          <IconButton class="add-project-folder" type="text" :loading="picking" :disabled="saving || roots.length >= 32" @click="pickFolder" :text="t('workspace.taskAgentSpace.add_local_folder')"><template #icon><Plus /></template></IconButton>
        </div>
      </a-form-item>
      <p class="project-folder-hint">{{ t('workspace.taskAgentSpace.project_folders_hint') }}</p>
      <p v-if="project" class="project-folder-hint">{{ t('workspace.taskAgentSpace.project_edit_hint') }}</p>
      <a-alert v-if="error" type="error" show-icon :message="t('workspace.taskAgentSpace.' + error)" />
    </a-form>
  </a-modal>
</template>
<style scoped>
.project-form { padding-top: 8px; }
.project-form :deep(.ant-input-affix-wrapper) { min-height: 40px; border-radius: 10px; }
.project-form :deep(.ant-input-prefix) { margin-right: 10px; color: var(--site-secondary-text-color); }
.project-folders-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; font-size: 13px; font-weight: 500; }
.project-folders-device { display: inline-flex; align-items: center; gap: 6px; color: var(--site-secondary-text-color); font-weight: 400; }
.project-folder-list { display: flex; flex-direction: column; max-height: 45vh; overflow-y: auto; border: var(--light-border); border-radius: 10px; }
.project-folder-row { display: flex; align-items: center; gap: 10px; min-height: 48px; padding: 8px 12px; border-bottom: var(--light-border); }
.project-folder-row:hover, .project-folder-row:focus-within { background: var(--more-hover-background); }
.project-folder-row:focus-visible { outline: 2px solid var(--color-primary); outline-offset: -2px; }
.project-folder-icon { flex-shrink: 0; color: var(--site-secondary-text-color); font-size: 18px; }
.project-folder-row strong { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; font-weight: 500; }
.project-primary-badge { padding: 2px 8px; border: var(--light-border); border-radius: 8px; white-space: nowrap; font-size: 12px; color: var(--site-secondary-text-color); }
:deep(.project-folder-action) { flex-shrink: 0; opacity: 0; pointer-events: none; }
.project-folder-row:hover :deep(.project-folder-action), .project-folder-row:focus-within :deep(.project-folder-action) { opacity: 1; pointer-events: auto; }
.project-folder-list > :deep(.icon-button-trigger) { align-self: flex-start; margin: 8px 12px; }
.project-folder-hint { color: var(--site-secondary-text-color); font-size: 12px; line-height: 1.65; }
@media (hover: none) { :deep(.project-folder-action) { opacity: 1; pointer-events: auto; } }
</style>
