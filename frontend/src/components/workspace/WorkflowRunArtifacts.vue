<script setup>
import { onMounted, onBeforeUnmount, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { workflowRunRecordAPI } from '@/api/workflow'
import { createRunArtifacts, formatArtifactSize, artifactSourceLabel } from '@/utils/workflowArtifacts'

const props = defineProps({ rid: { type: String, default: '' }, revision: { type: Number, default: 0 }, status: { type: String, default: '' } })
const { t, te, tm } = useI18n()
const sourceLabel = source => artifactSourceLabel(source, t, te, Object.keys(tm('components.nodes')))
const state = shallowRef({ artifacts: [], error: '', pending: '' })
const files = createRunArtifacts(workflowRunRecordAPI, value => { state.value = value })
let stop
onMounted(() => {
  stop = watch(() => [props.rid, props.revision, props.status], (value, previous) => {
    if (!previous || value[0] !== previous[0]) files.select(props.rid)
    else files.refresh()
  }, { immediate: true, flush: 'sync' })
})
onBeforeUnmount(() => { stop?.(); files.dispose() })
</script>

<template>
  <section v-if="state.artifacts.length || state.error" class="run-artifacts" :aria-label="t('workspace.workflowSpace.artifacts_title')">
    <h4 v-if="state.artifacts.length">{{ t('workspace.workflowSpace.artifacts_title') }}</h4>
    <div v-for="artifact in state.artifacts" :key="artifact.path" class="artifact-row">
      <div class="artifact-info">
        <strong :title="artifact.path">{{ artifact.name }}</strong>
        <span class="artifact-meta">{{ formatArtifactSize(artifact.size) }}<span v-if="!artifact.exists"> · {{ t('workspace.workflowSpace.artifact_missing') }}</span></span>
        <small v-if="artifact.sources?.length">{{ artifact.sources.map(sourceLabel).join(' · ') }}</small>
      </div>
      <a-space>
        <a-button size="small" :disabled="!artifact.exists || !!state.pending" @click="files.open(artifact, 'open')">{{ t('workspace.workflowSpace.artifact_open') }}</a-button>
        <a-button size="small" :disabled="!artifact.parent_exists || !!state.pending" @click="files.open(artifact, 'folder')">{{ t('workspace.workflowSpace.artifact_folder') }}</a-button>
      </a-space>
    </div>
    <div v-if="state.error" role="alert" class="artifact-error">
      {{ t(`workspace.workflowSpace.artifact_${state.error}_error`) }}
      <a-button type="link" size="small" @click="files.refresh()">{{ t('workspace.workflowSpace.artifact_retry') }}</a-button>
    </div>
  </section>
</template>

<style scoped>
.run-artifacts { margin-top: 20px; border-top: 1px solid #e8e8e8; padding-top: 12px; }
h4 { margin: 0 0 8px; }
.artifact-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; }
.artifact-info { min-width: 0; }
.artifact-info strong { overflow-wrap: anywhere; }
.artifact-meta { margin-left: 10px; color: #666; font-size: 12px; }
small { display: block; color: #666; overflow-wrap: anywhere; }
.artifact-error { color: #8a3434; }
@media (max-width: 600px) { .artifact-row { align-items: start; flex-direction: column; } }
</style>
