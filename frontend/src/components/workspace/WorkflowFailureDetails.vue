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
      <span v-if="failure.nodeId"> ({{ failure.nodeId }})</span>
      <div v-if="failure.code || failure.exceptionType">
        {{ [failure.code, failure.exceptionType].filter(Boolean).join(' · ') }}
      </div>
      <div class="workflow-failure-cause">{{ failure.code === 'WORKFLOW_INTERRUPTED' ? t('workspace.workflowSpace.interrupted_message') : failure.message || t('workspace.workflowSpace.failure_no_details') }}</div>
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
</style>
