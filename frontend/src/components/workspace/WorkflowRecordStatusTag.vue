<script setup>
import { useI18n } from 'vue-i18n'

const props = defineProps({
  status: {
    type: String,
    required: true,
  },
})

const { t } = useI18n()
const statusColor = {
  NOT_STARTED: 'purple',
  QUEUED: 'orange',
  RUNNING: 'blue',
  FINISHED: 'green',
  FAILED: 'red',
  STOPPING: 'orange',
  STOPPED: 'pink',
}
</script>

<template>
  <a-tag :color="statusColor[status]" :bordered="false">
    {{ t(`components.workspace.workflowRunRecordsDrawer.status_${status.toLowerCase()}`) }}
  </a-tag>
</template>