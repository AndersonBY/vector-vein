<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { PreviewOpen } from '@/icons'
import { workflowAPI } from '@/api/workflow'
import CanvasPreview from './CanvasPreview.vue'

const props = defineProps({
  workflow: { type: Object, default: null },
  workflowId: { type: String, default: '' },
  title: { type: String, default: '' },
})
const { t } = useI18n()
const open = ref(false)
const loading = ref(false)
const failed = ref(false)
const definition = ref(null)
const displayTitle = computed(() => props.title || props.workflow?.title || t('workspace.canvasPreview.workflow'))
let requestVersion = 0

const loadPreview = async () => {
  const version = ++requestVersion
  definition.value = null
  failed.value = false
  loading.value = true
  try {
    let workflow = props.workflow
    if (!workflow) {
      const response = await workflowAPI('get', { wid: props.workflowId })
      if (response.status !== 200) throw new Error('Workflow unavailable')
      workflow = response.data
    }
    if (version !== requestVersion || !open.value) return
    if (!Array.isArray(workflow?.data?.nodes)) throw new Error('Missing workflow definition')
    definition.value = workflow.data
  } catch {
    if (version === requestVersion && open.value) failed.value = true
  } finally {
    if (version === requestVersion) loading.value = false
  }
}
const openPreview = () => {
  open.value = true
  loadPreview()
}
watch(open, value => { if (!value) requestVersion++ }, { flush: 'sync' })
watch(() => [props.workflow, props.workflowId], () => { if (open.value) loadPreview() })
onBeforeUnmount(() => { requestVersion++ })
</script>

<template>
  <slot :open="openPreview">
    <a-tooltip :title="t('workspace.canvasPreview.open')">
      <a-button type="text" size="small" :aria-label="`${t('workspace.canvasPreview.open')} · ${displayTitle}`"
        @click.stop="openPreview">
        <template #icon><PreviewOpen /></template>
      </a-button>
    </a-tooltip>
  </slot>
  <!-- The canvas measures handle positions without the modal's scale animation. -->
  <a-modal v-model:open="open" :title="t('workspace.canvasPreview.title', { title: displayTitle })"
    :footer="null" width="85vw" transition-name="" destroy-on-close>
    <template v-if="open">
      <a-skeleton v-if="loading" active :paragraph="{ rows: 6 }" />
      <a-alert v-else-if="failed" type="error" :message="t('workspace.canvasPreview.load_failed')">
        <template #action><a-button size="small" @click="loadPreview">{{ t('workspace.canvasPreview.retry') }}</a-button></template>
      </a-alert>
      <CanvasPreview v-else-if="definition" :workflow="definition" height="65vh" />
    </template>
  </a-modal>
</template>
