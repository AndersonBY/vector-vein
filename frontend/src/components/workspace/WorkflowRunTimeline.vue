<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getWorkflowTimeline, getTimelineNodeLabel } from '@/utils/workflowTimeline'

const props = defineProps({ snapshot: { type: Object, default: () => ({}) }, active: Boolean, fresh: Boolean, status: { type: String, default: '' } })
const { t, te } = useI18n()
const now = ref(Date.now())
const open = ref(['timeline'])
let timer
watch(() => props.active, active => {
  clearInterval(timer)
  now.value = Date.now()
  if (active) {
    open.value = ['timeline']
    timer = setInterval(() => { now.value = Date.now() }, 1000)
  }
}, { immediate: true })
onBeforeUnmount(() => clearInterval(timer))
const rows = computed(() => getWorkflowTimeline(props.snapshot, { active: props.active, status: props.status, now: now.value, fresh: props.fresh }))
const completed = computed(() => rows.value.filter(row => ['SUCCEEDED', 'FAILED', 'SKIPPED'].includes(row.status)).length)
const runningNames = computed(() => rows.value.filter(row => ['RUNNING', 'WAITING'].includes(row.status)).map(row => `${getTimelineNodeLabel(row, t, te)} (${t(`workspace.workflowSpace.timeline_${row.status.toLowerCase()}`)})`).join(' · '))
const time = value => value === null ? '—' : new Date(value).toLocaleTimeString()
</script>

<template>
  <a-collapse v-if="rows.length" v-model:activeKey="open" class="run-timeline">
    <a-collapse-panel key="timeline">
      <template #header>
        <span>{{ t('workspace.workflowSpace.timeline_title') }} · {{ t('workspace.workflowSpace.timeline_completed', { completed, total: rows.length }) }}</span>
        <span v-if="runningNames" class="running-names"> · {{ runningNames }}</span>
      </template>
      <div class="timeline-scroll">
        <table>
          <thead><tr><th>{{ t('workspace.workflowSpace.timeline_node') }}</th><th>{{ t('workspace.workflowSpace.timeline_state') }}</th><th>{{ t('workspace.workflowSpace.timeline_elapsed') }}</th><th>{{ t('workspace.workflowSpace.timeline_started') }}</th><th>{{ t('workspace.workflowSpace.timeline_finished') }}</th></tr></thead>
          <tbody><tr v-for="row in rows" :key="row.id">
            <td><strong>{{ getTimelineNodeLabel(row, t, te) }}</strong><small>{{ row.id }}</small></td>
            <td>{{ t(`workspace.workflowSpace.timeline_${row.status.toLowerCase()}`) }}</td>
            <td>{{ row.elapsed === null ? '—' : `${row.elapsed.toFixed(1)} s` }}</td>
            <td>{{ time(row.startedAt) }}</td><td>{{ time(row.finishedAt) }}</td>
          </tr></tbody>
        </table>
      </div>
      <p v-if="rows.some(row => row.elapsed === null || row.startedAt === null || row.finishedAt === null)" class="timing-note">{{ t('workspace.workflowSpace.timeline_timing_unavailable') }}</p>
    </a-collapse-panel>
  </a-collapse>
</template>

<style scoped>
.run-timeline { margin-bottom: 16px; }
.timeline-scroll { overflow-x: auto; max-height: 360px; }
table { width: 100%; border-collapse: collapse; text-align: left; }
th, td { padding: 8px 12px; border-bottom: 1px solid #e8e8e8; vertical-align: top; }
th { font-weight: 500; white-space: nowrap; }
small { display: block; color: #666; overflow-wrap: anywhere; }
.running-names { font-weight: 400; overflow-wrap: anywhere; }
.timing-note { color: #666; margin: 8px 12px 0; }
</style>
