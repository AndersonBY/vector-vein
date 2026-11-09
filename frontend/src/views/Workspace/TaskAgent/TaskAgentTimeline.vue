<script setup>
import IconButton from '@/components/IconButton.vue'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import TextOutput from '@/components/TextOutput.vue'
import TaskAgentModelError from './TaskAgentModelError.vue'
import { commandStatus, isMcpUnknown, taskActivityRows, taskConversationRows, toolDisplaySummary, toolStatusKey } from '@/utils/taskAgentTimeline'
import { formatTaskTime } from '@/utils/taskAgentPresentation'
import { taskModelFailure } from '@/utils/taskAgentErrors'
import { CheckOne, LoadingFour, Caution, Tool, Robot, Down, Copy } from '@/icons'
const props = defineProps({ entries: { type: Array, default: () => [] }, modelConfig: { type: Object, default: () => ({}) }, nested: Boolean })
const emit = defineEmits(['result', 'preview', 'subtask', 'layout-interaction'])
const { t, te, locale } = useI18n()
const expanded = ref(new Set())
const copied = ref(null)
const historyExpanded = ref(new Map())
const rows = computed(() => props.nested ? taskActivityRows(props.entries) : taskConversationRows(props.entries))
const followsWithActivity = (entry, index) => {
  const next = rows.value[index + 1]
  return entry.kind === 'assistant' && next?.kind === 'activity' && next.turn_id === entry.turn_id
    && entry.cycle === next.entries[0]?.cycle
}
const historyIsExpanded = entry => historyExpanded.value.get(entry.id) ?? entry.attention
const toggleHistory = entry => {
  historyExpanded.value.set(entry.id, !historyIsExpanded(entry))
  emit('layout-interaction')
}
const title = item => item.display_name || (te('workspace.taskAgentSpace.tool_' + item.tool_name) ? t('workspace.taskAgentSpace.tool_' + item.tool_name) : item.tool_name)
const running = item => ['pending', 'running'].includes(item.status) || ['ADMITTED', 'DISPATCHING'].includes(item.mcp_run?.status) || ['running', 'stopping'].includes(commandStatus(item))
const failed = item => ['error', 'cancelled'].includes(item.status) || ['FAILED', 'CANCELLED'].includes(item.mcp_run?.status) || isMcpUnknown(item) || ['unknown', 'failed', 'timeout'].includes(commandStatus(item))
const toggle = id => {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id); else next.add(id)
  expanded.value = next
  emit('layout-interaction')
}
const activityText = row => {
  const errors = row.entries.filter(failed).length
  const active = row.entries.filter(running).length
  return t('workspace.taskAgentSpace.' + (errors ? 'activity_errors' : active ? 'activity_running' : 'activity_done'), { count: row.entries.length, errors, active })
}
const copy = async entry => {
  try { await navigator.clipboard.writeText(entry.text || ''); copied.value = entry.id } catch { copied.value = null }
}
</script>
<template>
  <div class="task-timeline">
    <div v-if="!nested" class="timeline-toolbar">{{ t('workspace.taskAgentSpace.task_progress') }}</div>
    <article v-for="(entry, index) in rows" :key="entry.id" class="timeline-entry" :class="[entry.kind, { 'before-activity': followsWithActivity(entry, index) }]" :data-entry-id="entry.id">
      <template v-if="entry.kind === 'history'">
        <button type="button" class="history-disclosure" :aria-expanded="historyIsExpanded(entry)" @click="toggleHistory(entry)">
          <Down :class="{ collapsed: !historyIsExpanded(entry) }" /><span>{{ t('workspace.taskAgentSpace.intermediate_steps') }}</span>
          <Caution v-if="entry.attention" class="attention" />
          <small><span v-if="entry.duration">{{ t('workspace.taskAgentSpace.activity_duration', { seconds: entry.duration }) }}</span><span v-if="entry.cycles">{{ t('workspace.taskAgentSpace.activity_cycles', { count: entry.cycles }) }}</span></small>
        </button>
        <TaskAgentTimeline v-if="historyIsExpanded(entry)" class="history-content" :entries="entry.entries" :model-config="modelConfig" nested @result="emit('result', $event)" @preview="emit('preview', $event)" @subtask="emit('subtask', $event)" @layout-interaction="emit('layout-interaction')" />
      </template>
      <template v-else-if="['user', 'assistant'].includes(entry.kind)">
        <div class="message-content"><div v-if="entry.kind === 'user'" class="user-text">{{ entry.text }}</div><TextOutput v-else :text="entry.text" :show-copy="false" /></div>
        <div v-if="entry.attachments?.length" class="attachments"><a-button v-for="file in entry.attachments" :key="file.path" size="small" @click="emit('preview', file.path)">{{ file.name }}</a-button></div>
        <div class="message-actions"><time>{{ formatTaskTime(entry.created_at, locale) }}</time><IconButton :aria-label="t('workspace.taskAgentSpace.copy_message')" @click="copy(entry)" size="small" :text="t('workspace.taskAgentSpace.copy_message')"><template #icon><CheckOne v-if="copied === entry.id" /><Copy v-else /></template></IconButton></div>
      </template>
      <template v-else-if="entry.kind === 'activity'">
        <button type="button" class="activity-summary" :aria-expanded="expanded.has(entry.id)" @click="toggle(entry.id)">
          <LoadingFour v-if="entry.entries.some(running)" spin /><Caution v-else-if="entry.entries.some(failed)" /><Tool v-else />
          <span>{{ activityText(entry) }}</span><time>{{ formatTaskTime(entry.created_at, locale) }}</time><Down :class="{ rotated: expanded.has(entry.id) }" />
        </button>
        <div v-if="expanded.has(entry.id)" class="activity-items">
          <button v-for="tool in entry.entries" :key="tool.id" type="button" class="tool-row" @click="emit('result', tool)">
            <Caution v-if="failed(tool)" class="attention" /><LoadingFour v-else-if="running(tool)" spin /><CheckOne v-else />
            <strong>{{ title(tool) }}</strong><span class="tool-summary">{{ toolDisplaySummary(tool) }}</span><span v-if="['error', 'cancelled'].includes(tool.status) || ['FAILED', 'CANCELLED'].includes(tool.mcp_run?.status)" class="attention">{{ t('workspace.taskAgentSpace.' + toolStatusKey(tool)) }}</span><span v-else-if="isMcpUnknown(tool)" class="attention">{{ t('workspace.taskAgentSpace.mcp_outcome_unknown') }}</span><span v-else-if="commandStatus(tool) === 'unknown'" class="attention">{{ t('workspace.taskAgentSpace.command_unknown') }}</span><span class="open-detail">↗</span>
          </button>
        </div>
      </template>
      <button v-else-if="entry.kind === 'sub_agent'" type="button" class="subtask-row" @click="emit('subtask', entry)"><Robot /><span>{{ t('workspace.taskAgentSpace.sub_agent') }}</span><LoadingFour v-if="entry.status === 'running'" spin /><span class="subtask-status">{{ t('workspace.taskAgentSpace.child_' + entry.status) }}</span><span class="open-detail">↗</span></button>
      <div v-else-if="entry.kind === 'question'" class="historical-question">{{ entry.text }}</div>
      <TaskAgentModelError v-else-if="taskModelFailure(entry)" :failure="taskModelFailure(entry)" :model-config="modelConfig" />
      <a-alert v-else-if="entry.kind === 'error'" type="error" show-icon :message="t('workspace.taskAgentSpace.status_FAILED')" :description="entry.text" />
      <p v-else-if="entry.kind === 'memory_compact_completed'" class="tool-note">{{ t('workspace.taskAgentSpace.context_compacted') }}</p>
      <p v-else-if="entry.kind === 'run_cancelled'" class="tool-note">{{ t('workspace.taskAgentSpace.status_INTERRUPTED') }}</p>
    </article>
  </div>
</template>
<style scoped>
.task-timeline { display: flex; flex-direction: column; min-width: 0; }
.timeline-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 8px 0 20px; font-size: 12px; color: var(--site-secondary-text-color); }
.history-disclosure { display: flex; align-items: center; gap: 7px; width: 100%; min-height: 32px; padding: 4px 0; border: 0; border-bottom: var(--light-border); background: transparent; color: var(--site-secondary-text-color); text-align: left; cursor: pointer; font-size: 13px; }
.history-disclosure > svg { width: 14px; height: 14px; flex-shrink: 0; }.history-disclosure .collapsed { transform: rotate(-90deg); }.history-disclosure small { display: flex; gap: 9px; margin-left: auto; font-size: 11px; font-variant-numeric: tabular-nums; }.history-content { padding: 0 12px; }
.timeline-entry { min-width: 0; margin: 10px 0; overflow-wrap: anywhere; }
.timeline-entry.before-activity { position: relative; margin-bottom: 0; }
.timeline-entry.before-activity + .timeline-entry.activity { margin-top: 4px; }
.before-activity > .message-actions { position: absolute; bottom: 100%; right: 0; margin: 0; background: var(--component-background); }
.timeline-entry.user { align-self: flex-end; max-width: 85%; margin: 8px 0 18px auto; }
.user .message-content { padding: 12px 16px; border-radius: 18px 18px 4px 18px; background: linear-gradient(135deg, #95de64, #b7eb8f); color: #2f2f2f; }
.user-text { white-space: pre-wrap; }
.message-content { font-size: 14px; line-height: 1.75; }
.message-content :deep(.markdown-body) { font-family: inherit; font-size: 14px; background: transparent; color: inherit; }
.message-content :deep(.markdown-body > :first-child) { margin-top: 0; }
.message-content :deep(.markdown-body > :last-child) { margin-bottom: 0; }
.user .message-content :deep(p:last-child) { margin-bottom: 0; }
.message-actions { display: flex; gap: 8px; align-items: center; margin-top: 6px; color: var(--site-secondary-text-color); font-size: 11px; }
.user .message-actions { justify-content: flex-end; }
.message-actions :deep(button) { display: grid; place-items: center; width: 26px; height: 26px; border: 0; border-radius: 4px; background: transparent; color: inherit; cursor: pointer; }
.attachments { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.activity-summary, .tool-row, .subtask-row { display: flex; align-items: center; gap: 8px; width: 100%; min-width: 0; padding: 8px 0; border: 0; background: transparent; color: var(--site-secondary-text-color); text-align: left; cursor: pointer; font-size: 13px; line-height: 1.5; }
.activity-summary > span:first-of-type { flex: 1; }
.activity-summary time { font-size: 11px; visibility: hidden; }.activity-summary:hover time, .activity-summary:focus-visible time { visibility: visible; }
.activity-summary > svg, .tool-row > svg, .subtask-row > svg { flex-shrink: 0; width: 15px; height: 15px; }
.activity-summary .rotated { transform: rotate(180deg); }
.activity-items { padding-left: 14px; margin-left: 7px; border-left: var(--light-border); max-height: 340px; overflow: auto; overscroll-behavior: contain; }
.tool-row { padding: 8px; border-radius: 6px; }
.tool-row strong { flex-shrink: 0; font-size: 12px; font-weight: 500; color: var(--site-text-color); }
.tool-summary { min-width: 0; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12px; }
.open-detail { flex-shrink: 0; margin-left: auto; }
.subtask-row { padding: 10px 12px; border: var(--light-border); border-radius: 8px; }
.subtask-status { font-size: 12px; }
.tool-note { margin: 3px 8px 8px; font-size: 12px; color: var(--site-secondary-text-color); }
.attention { color: var(--error-color, #b65c26); }
.historical-question { padding: 10px 0; border-bottom: var(--light-border); font-size: 14px; white-space: pre-wrap; }
button:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
@media (hover: hover) and (pointer: fine) {
  .message-actions { opacity: 0; pointer-events: none; }
  .timeline-entry:hover > .message-actions,
  .timeline-entry:focus-within > .message-actions { opacity: 1; pointer-events: auto; }
}
@media (hover: hover) and (pointer: fine) { .tool-row:hover, .message-actions :deep(button):hover, .subtask-row:hover { background: var(--more-hover-background); }.activity-summary:hover { color: var(--site-text-color); } }
.theme-dark .user .message-content { background: #263b32; color: #d5dfd9; box-shadow: inset 0 0 0 1px #3a5245; }
</style>
