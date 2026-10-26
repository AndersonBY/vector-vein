<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import WorkflowFailureDetails from '@/components/workspace/WorkflowFailureDetails.vue'

const props = defineProps({
  status: { type: String, required: true },
  snapshot: { type: Object, default: () => ({}) },
  recordWorkflowVersion: { type: [Number, null], default: null },
})
const emit = defineEmits(['close'])
const { t } = useI18n()
const alertType = computed(() => ({
  FINISHED: 'success', FAILED: 'error', STOPPED: 'warning', STOPPING: 'warning',
})[props.status] || 'info')
</script>

<template>
  <a-alert :type="alertType" banner="" show-icon closable @close="emit('close')">
    <template #message>
      <a-tooltip :title="t('workspace.workflowSpace.record_version')">
        <a-tag v-if="recordWorkflowVersion">v{{ recordWorkflowVersion }}</a-tag>
      </a-tooltip>
      <span>
        {{ t('workspace.workflowSpace.record_status', {
          status: t(`components.workspace.workflowRunRecordsDrawer.status_${status.toLowerCase()}`)
        }) }}
      </span>
    </template>
    <template v-if="status === 'FAILED'" #description>
      <WorkflowFailureDetails :snapshot="snapshot" />
    </template>
  </a-alert>
</template>
