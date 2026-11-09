<script setup>
import IconButton from '@/components/IconButton.vue'
import { OffScreenOne, Refresh } from '@/icons'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { v4 as uuidv4 } from 'uuid'
import { taskAgentAPI } from '@/api/taskAgent'

const props = defineProps({
  taskId: { type: String, required: true },
  tokenUsage: { type: Object, default: null },
  contextWindow: { type: Number, default: null },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh'])
const { t } = useI18n()

const open = ref(false)
const loading = ref(false)
const loadFailed = ref(false)
const contextData = ref(null)
const liveTokenUsage = ref(null)
const liveCompaction = ref(null)

const compacting = ref(false)
const pendingAttempt = ref(null)
const compactionState = ref('')
const compactionRequestId = ref('')

const validCount = value => Number.isSafeInteger(value) && value >= 0 ? value : null
const validLimit = value => Number.isSafeInteger(value) && value > 0 ? value : null

const effectiveUsage = computed(() => liveTokenUsage.value || props.tokenUsage || null)

const hasNativeEstimate = computed(() => validCount(contextData.value?.estimates?.total) !== null)

const usedTokens = computed(() => {
  const estimate = validCount(contextData.value?.estimates?.total)
  if (estimate !== null) return estimate
  return validCount(effectiveUsage.value?.latest_input_tokens)
})

const sourceNote = computed(() => {
  if (hasNativeEstimate.value) return t('workspace.taskAgentSpace.context_current_estimate')
  if (validCount(effectiveUsage.value?.latest_input_tokens) !== null) return t('workspace.taskAgentSpace.context_last_request')
  return ''
})

const totalWindow = computed(() => {
  const nativeWindow = validLimit(contextData.value?.limits?.contextWindow)
  if (nativeWindow !== null) return nativeWindow
  return validLimit(props.contextWindow)
})

const compactionThreshold = computed(() => validLimit(contextData.value?.limits?.compactionThreshold))

const contextPercent = computed(() => {
  if (usedTokens.value === null || totalWindow.value === null) return null
  return Math.round((usedTokens.value / totalWindow.value) * 100)
})

const clampedPercent = computed(() => {
  if (contextPercent.value === null) return null
  return Math.max(0, Math.min(100, contextPercent.value))
})

const contextTokensSummary = computed(() => {
  if (usedTokens.value === null) return t('workspace.taskAgentSpace.context_unknown')
  const usedText = usedTokens.value.toLocaleString()
  if (totalWindow.value !== null) {
    return t('workspace.taskAgentSpace.context_tokens_pair', {
      used: usedText,
      total: totalWindow.value.toLocaleString(),
    })
  }
  return usedText
})

const cacheReadTokens = computed(() => validCount(effectiveUsage.value?.cache_read_tokens))
const cacheInputTokens = computed(() => validLimit(effectiveUsage.value?.cache_input_tokens))
const reportedCalls = computed(() => validCount(effectiveUsage.value?.reported_calls) ?? 0)
const cacheMissingCalls = computed(() => validCount(effectiveUsage.value?.cache_missing_calls) ?? 0)

const cacheHitRate = computed(() => {
  if (
    reportedCalls.value <= 0 ||
    cacheInputTokens.value === null ||
    cacheReadTokens.value === null ||
    cacheReadTokens.value > cacheInputTokens.value
  ) {
    return '—'
  }
  return `${Math.round((cacheReadTokens.value / cacheInputTokens.value) * 1000) / 10}%`
})

const cacheTokensSummary = computed(() => {
  if (cacheHitRate.value === '—') return ''
  return t('workspace.taskAgentSpace.context_tokens_pair', {
    used: cacheReadTokens.value.toLocaleString(),
    total: cacheInputTokens.value.toLocaleString(),
  })
})

const currentContextVersion = computed(() => {
  const ver = contextData.value?.contextVersion
  return typeof ver === 'string' && /^[0-9a-f]{64}$/i.test(ver) ? ver : ''
})

const isPendingCompaction = computed(() => compactionState.value === 'queued' || compactionState.value === 'running')

const canCompact = computed(() => {
  if (props.disabled || compacting.value || isPendingCompaction.value) return false
  if (compactionState.value === 'uncertain' && pendingAttempt.value) return true
  return Boolean(currentContextVersion.value)
})

const compactionStatusText = computed(() => {
  if (!compactionState.value) return ''
  return t(`workspace.taskAgentSpace.context_compact_${compactionState.value}`)
})

const buttonAriaLabel = computed(() => {
  const percentPart = contextPercent.value === null ? '' : ` ${contextPercent.value}%`
  return `${t('workspace.taskAgentSpace.context_title')}${percentPart} (${contextTokensSummary.value})`
})

let alive = true
let taskEpoch = 0
let fetchSeq = 0
let pollTimer = null

const stopTimer = () => {
  if (pollTimer !== null) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

const shouldPoll = () => alive && Boolean(props.taskId) && (open.value || isPendingCompaction.value)

const schedulePoll = () => {
  stopTimer()
  if (!shouldPoll()) return
  const expectedEpoch = taskEpoch
  pollTimer = setTimeout(() => {
    pollTimer = null
    if (!alive || expectedEpoch !== taskEpoch || !shouldPoll()) return
    fetchContext()
  }, 3000)
}

const applyCompactionFromServer = serverCompaction => {
  liveCompaction.value = serverCompaction || null
  if (!serverCompaction || typeof serverCompaction !== 'object') return
  const reqId = typeof serverCompaction.request_id === 'string' ? serverCompaction.request_id : ''
  const status = serverCompaction.status
  if (!reqId || !['queued', 'running', 'completed', 'failed'].includes(status)) return

  if (compactionRequestId.value && reqId === compactionRequestId.value) {
    const wasPending = isPendingCompaction.value || compactionState.value === 'uncertain'
    compactionState.value = status
    if (status === 'completed' || status === 'failed') {
      pendingAttempt.value = null
      if (wasPending) emit('refresh')
    }
    return
  }

  if (!compactionRequestId.value && (status === 'queued' || status === 'running')) {
    compactionRequestId.value = reqId
    compactionState.value = status
  }
}

const fetchContext = async () => {
  const tid = props.taskId
  if (!alive || !tid) return false
  const expectedEpoch = taskEpoch
  const seq = ++fetchSeq
  loading.value = true
  try {
    const response = await taskAgentAPI('task_context', { task_id: tid })
    if (!alive || expectedEpoch !== taskEpoch || seq !== fetchSeq) return false
    if (response?.status !== 200 || !response?.data?.context || typeof response.data.context.contextVersion !== 'string') {
      loadFailed.value = true
      return false
    }
    loadFailed.value = false
    contextData.value = response.data.context
    if (response.data.token_usage && typeof response.data.token_usage === 'object') {
      liveTokenUsage.value = response.data.token_usage
    }
    applyCompactionFromServer(response.data.compaction)
    return true
  } catch {
    if (alive && expectedEpoch === taskEpoch && seq === fetchSeq) {
      loadFailed.value = true
    }
    return false
  } finally {
    if (alive && expectedEpoch === taskEpoch && seq === fetchSeq) {
      loading.value = false
      schedulePoll()
    }
  }
}

const requestCompact = async () => {
  const tid = props.taskId
  if (!alive || !tid || !canCompact.value) return
  const expectedEpoch = taskEpoch

  const attempt =
    compactionState.value === 'uncertain' && pendingAttempt.value && pendingAttempt.value.task_id === tid
      ? pendingAttempt.value
      : {
          task_id: tid,
          action_id: uuidv4().replaceAll('-', ''),
          expected_context_version: currentContextVersion.value,
        }

  if (!attempt.expected_context_version) return

  pendingAttempt.value = attempt
  compacting.value = true
  try {
    const response = await taskAgentAPI('compact_context', {
      task_id: attempt.task_id,
      action_id: attempt.action_id,
      expected_context_version: attempt.expected_context_version,
    })
    if (!alive || expectedEpoch !== taskEpoch) return

    if (response?.status === 200 && response?.data?.compaction?.accepted) {
      const reqId = typeof response.data.compaction.requestId === 'string' ? response.data.compaction.requestId : ''
      compactionRequestId.value = reqId
      compactionState.value = 'queued'
      pendingAttempt.value = null
      emit('refresh')
      await fetchContext()
      return
    }

    if (response?.status === 409 && response?.data?.context_error === 'context_changed') {
      pendingAttempt.value = null
      compactionRequestId.value = ''
      compactionState.value = 'changed'
      await fetchContext()
      return
    }

    if (response?.status === 400 || response?.status === 404 || response?.status === 409) {
      pendingAttempt.value = null
      compactionRequestId.value = ''
      compactionState.value = 'failed'
      return
    }

    compactionState.value = 'uncertain'
  } catch {
    if (alive && expectedEpoch === taskEpoch) {
      compactionState.value = 'uncertain'
    }
  } finally {
    if (alive && expectedEpoch === taskEpoch) {
      compacting.value = false
      schedulePoll()
    }
  }
}

watch(open, isOpen => {
  if (!alive) return
  if (isOpen) {
    fetchContext()
  } else {
    schedulePoll()
  }
})

watch(() => [props.tokenUsage?.reported_calls, props.contextWindow], () => {
  const newerCalls = (props.tokenUsage?.reported_calls ?? 0) > (liveTokenUsage.value?.reported_calls ?? 0)
  const changedWindow = contextData.value && props.contextWindow !== contextData.value.limits?.contextWindow
  if (newerCalls || changedWindow) {
    contextData.value = null
    liveTokenUsage.value = null
  }
})

watch(
  () => props.taskId,
  () => {
    taskEpoch++
    fetchSeq++
    stopTimer()
    loading.value = false
    loadFailed.value = false
    contextData.value = null
    liveTokenUsage.value = null
    liveCompaction.value = null
    compacting.value = false
    pendingAttempt.value = null
    compactionState.value = ''
    compactionRequestId.value = ''
    if (open.value) {
      fetchContext()
    }
  },
)

onBeforeUnmount(() => {
  alive = false
  taskEpoch++
  fetchSeq++
  stopTimer()
})

defineExpose({
  open,
  loading,
  loadFailed,
  contextData,
  liveTokenUsage,
  usedTokens,
  totalWindow,
  compactionThreshold,
  contextPercent,
  clampedPercent,
  sourceNote,
  cacheHitRate,
  cacheMissingCalls,
  compactionState,
  compactionRequestId,
  pendingAttempt,
  canCompact,
  fetchContext,
  requestCompact,
})
</script>

<template>
  <a-popover
    v-model:open="open"
    :trigger="['hover', 'click']"
    placement="topRight"
    color="#303030"
    :overlay-style="{ maxWidth: 'min(296px, calc(100vw - 24px))' }"
    :overlay-inner-style="{ padding: '14px 16px', borderRadius: '10px', boxShadow: '0 5px 18px rgba(0, 0, 0, 0.22)' }"
  >
    <template #content>
      <div class="context-usage-panel">
        <div class="context-usage-section">
          <div class="context-usage-heading">
            <span>{{ t('workspace.taskAgentSpace.context_title') }}</span>
            <strong class="context-usage-value">{{ contextPercent === null ? '—' : `${contextPercent}%` }}</strong>
          </div>
          <div v-if="clampedPercent !== null" class="context-usage-track" aria-hidden="true">
            <span :style="{ width: `${clampedPercent}%` }"></span>
          </div>
          <div class="context-usage-counts">{{ contextTokensSummary }}</div>
          <div v-if="sourceNote" class="context-usage-note">{{ sourceNote }}</div>
          <div v-if="compactionThreshold !== null" class="context-usage-note">
            {{ t('workspace.taskAgentSpace.context_threshold', { count: compactionThreshold.toLocaleString() }) }}
          </div>
        </div>

        <div class="context-usage-section context-usage-divider">
          <div class="context-usage-heading">
            <span>{{ t('workspace.taskAgentSpace.context_cache_title') }}</span>
            <strong class="context-usage-value">{{ cacheHitRate }}</strong>
          </div>
          <div v-if="cacheTokensSummary" class="context-usage-counts">{{ cacheTokensSummary }}</div>
          <div class="context-usage-note">{{ t('workspace.taskAgentSpace.context_cache_note') }}</div>
          <div v-if="cacheMissingCalls > 0" class="context-usage-note context-usage-warning">
            {{ t('workspace.taskAgentSpace.context_cache_partial') }}
          </div>
        </div>

        <div v-if="loadFailed" class="context-usage-error" role="alert">
          <span>{{ t('workspace.taskAgentSpace.context_load_failed') }}</span>
          <IconButton type="text" size="small" class="context-inline-retry" :loading="loading" @click="fetchContext" :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
        </div>

        <div class="context-usage-section context-usage-divider context-usage-actions">
          <div class="context-usage-note">{{ t('workspace.taskAgentSpace.context_compact_hint') }}</div>
          <div v-if="compactionStatusText" class="context-compaction-status" :class="`is-${compactionState}`" role="status">
            <span>{{ compactionStatusText }}</span>
            <IconButton
              v-if="compactionState === 'uncertain' && pendingAttempt"
              type="text"
              size="small"
              class="context-inline-retry"
              :disabled="props.disabled || compacting"
              :loading="compacting"
              @click="requestCompact"
             :text="t('workspace.taskAgentSpace.retry')"><template #icon><Refresh /></template></IconButton>
          </div>
          <div class="context-action-buttons">
            <IconButton
              type="text"
              size="small"
              class="context-action-btn"
              :loading="loading"
              @click="fetchContext"
             :text="t('workspace.taskAgentSpace.context_refresh')"><template #icon><Refresh /></template></IconButton>
            <IconButton
              type="text"
              size="small"
              class="context-action-btn context-compact-btn"
              :disabled="!canCompact"
              :loading="compacting || isPendingCompaction"
              @click="requestCompact"
             :text="t('workspace.taskAgentSpace.context_compact')"><template #icon><OffScreenOne /></template></IconButton>
          </div>
        </div>
      </div>
    </template>

    <a-button
      type="text"
      class="context-usage-button"
      :aria-label="buttonAriaLabel"
      :aria-expanded="open"
      aria-haspopup="dialog"
    >
      <a-progress
        type="circle"
        :size="18"
        :stroke-width="12"
        :percent="clampedPercent ?? 0"
        :show-info="false"
        stroke-color="currentColor"
        trail-color="rgba(140, 140, 140, 0.25)"
        style="pointer-events: none"
        aria-hidden="true"
      />
    </a-button>
  </a-popover>
</template>

<style scoped>
.context-usage-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  padding: 0;
  border-radius: 6px;
  color: var(--site-secondary-text-color, #8c8c8c);
  flex-shrink: 0;
}

.context-usage-button:hover {
  color: var(--site-text-color, #262626);
}

.context-usage-button:focus-visible {
  outline: 2px solid var(--color-primary, #1677ff);
  outline-offset: 2px;
}

.context-usage-panel {
  width: 264px;
  max-width: 100%;
  color: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  line-height: 1.5;
}

.context-usage-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.context-usage-divider {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.14);
}

.context-usage-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.context-usage-value {
  font-size: 18px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.context-usage-track {
  height: 3px;
  margin: 2px 0 3px;
  overflow: hidden;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.18);
}

.context-usage-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: rgba(255, 255, 255, 0.88);
  transition: width 0.2s ease;
}

.context-usage-counts {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  opacity: 0.88;
}

.context-usage-note {
  font-size: 11px;
  opacity: 0.62;
  overflow-wrap: anywhere;
}

.context-usage-warning {
  opacity: 0.85;
  color: #ffd666;
}

.context-usage-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 10px;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(255, 77, 79, 0.18);
  color: #ffccc7;
  font-size: 11px;
}

.context-compaction-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 2px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.88);
}

.context-compaction-status.is-failed,
.context-compaction-status.is-changed,
.context-compaction-status.is-uncertain {
  color: #ffd666;
}

.context-action-buttons {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 4px;
}

:deep(.context-action-btn),
:deep(.context-inline-retry) {
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.88) !important;
  font-size: 12px;
}

:deep(.context-action-btn):hover:not(:disabled),
:deep(.context-inline-retry):hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.14) !important;
  color: #ffffff !important;
}

:deep(.context-compact-btn) {
  background: rgba(255, 255, 255, 0.1) !important;
}

:deep(.context-action-btn):disabled {
  color: rgba(255, 255, 255, 0.35) !important;
  background: transparent !important;
}

@media (prefers-reduced-motion: reduce) {
  .context-usage-track span,
  .context-usage-button :deep(*) {
    transition: none !important;
    animation: none !important;
  }
}
</style>
