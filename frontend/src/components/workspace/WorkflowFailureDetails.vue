<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getWorkflowFailures, getWorkflowTaskTitleKey } from '@/utils/workflowFailures'

const props = defineProps({
  snapshot: { type: Object, default: () => ({}) },
})
const { t, te } = useI18n()
const failures = computed(() => getWorkflowFailures(props.snapshot))
const nodeTitle = (failure) => {
  if (failure.code === 'WORKFLOW_INTERRUPTED') return t('workspace.workflowSpace.interrupted_title')
  const key = getWorkflowTaskTitleKey(failure.taskName)
  return failure.nodeName || (key && te(key) ? t(key) : failure.taskName) ||
    t('workspace.workflowSpace.failure_unknown_node')
}
</script>

<template>
  <div class="workflow-failure-details">
    <div v-for="(failure, index) in failures" :key="index" class="workflow-failure">
      <strong>{{ t('workspace.workflowSpace.record_error_task', { task: nodeTitle(failure) }) }}</strong>
      <div class="workflow-failure-cause">{{ failure.code === 'WORKFLOW_INTERRUPTED' ? t('workspace.workflowSpace.interrupted_message') : failure.message || t('workspace.workflowSpace.failure_no_details') }}</div>
      <details v-if="failure.nodeId || failure.code || failure.exceptionType" class="failure-diagnostics">
        <summary>{{ t('workspace.workflowSpace.error_details') }}</summary>
        <div v-if="failure.nodeId">{{ t('workspace.workflowSpace.timeline_node') }} ID: {{ failure.nodeId }}</div>
        <div>{{ [failure.code, failure.exceptionType].filter(Boolean).join(' · ') }}</div>
      </details>
    </div>
    <div v-if="failures.length === 0">{{ t('workspace.workflowSpace.failure_no_details') }}</div>
    <div>{{ t('workspace.workflowSpace.failure_rerun_hint') }}</div>
  </div>
</template>

<style scoped>
.workflow-failure-details {
  overflow-wrap: anywhere;
}
.workflow-failure {
  margin-bottom: 8px;
}
.workflow-failure-cause {
  white-space: pre-wrap;
}
.failure-diagnostics { margin-top: 4px; color: var(--site-secondary-text-color); }
.failure-diagnostics summary { cursor: pointer; }
</style>
