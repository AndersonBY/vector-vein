<script setup>
import { reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
const props = defineProps({ runs: { type: Array, default: () => [] }, busy: Boolean, disabled: Boolean })
const emit = defineEmits(['feedback'])
const { t } = useI18n()
const answers = reactive({})
const key = (checkpoint, node) => checkpoint.run_id + ':' + checkpoint.generation + ':' + node
const canAnswer = checkpoint => checkpoint.questions.every(question => answers[key(checkpoint, question.node_id)]?.trim())
const submit = checkpoint => {
  if (!canAnswer(checkpoint) || props.busy || props.disabled) return
  emit('feedback', { run_id: checkpoint.run_id, generation: checkpoint.generation,
    answers: checkpoint.questions.map(question => ({ node_id: question.node_id, content: answers[key(checkpoint, question.node_id)].trim() })) })
}
watch(() => props.runs, runs => {
  const keys = new Set(runs.flatMap(run => run.feedback.flatMap(checkpoint => checkpoint.questions.map(question => key(checkpoint, question.node_id)))))
  for (const name of Object.keys(answers)) if (!keys.has(name)) delete answers[name]
})
</script>
<template>
  <section v-if="runs.length" class="workflow-runs" :aria-label="t('workspace.taskAgentSpace.workflow_runs')">
    <h3>{{ t('workspace.taskAgentSpace.workflow_runs') }}</h3>
    <article v-for="run in runs" :key="run.job_id" class="workflow-run">
      <header><router-link :to="{ name: 'WorkflowUse', params: { workflowId: run.workflow_id }, query: { rid: run.run_id } }">{{ run.title }}</router-link><span>{{ t('workspace.taskAgentSpace.workflow_status_' + run.status) }}</span></header>
      <div v-for="checkpoint in run.feedback" :key="checkpoint.run_id + ':' + checkpoint.generation" class="workflow-feedback">
        <label v-for="question in checkpoint.questions" :key="question.node_id" class="feedback-field">
          <span>{{ question.prompt || t('workspace.taskAgentSpace.workflow_review') }}</span>
          <a-textarea v-model:value="answers[key(checkpoint, question.node_id)]" :aria-label="String(question.prompt || t('workspace.taskAgentSpace.your_answer'))" :auto-size="{ minRows: 2, maxRows: 6 }" :disabled="busy || disabled" />
        </label>
        <p v-if="checkpoint.resume_ready && !checkpoint.questions.length">{{ t('workspace.taskAgentSpace.workflow_resume_ready') }}</p>
        <a-button type="primary" :loading="busy" :disabled="disabled || !canAnswer(checkpoint)" @click="submit(checkpoint)">{{ t('workspace.taskAgentSpace.continue_workflow') }}</a-button>
      </div>
      <p v-if="run.status === 'UNKNOWN'" class="unknown-outcome">{{ t('workspace.taskAgentSpace.workflow_unknown') }}</p>
    </article>
  </section>
</template>
<style scoped>
.workflow-runs { margin: 24px 0; }
h3 { font-size: 15px; font-weight: 600; margin: 0 0 12px; }
.workflow-run { padding: 14px 16px; margin-top: 10px; border: var(--border-color); border-radius: 6px; }
header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
header a { overflow-wrap: anywhere; }
header span { flex-shrink: 0; font-size: 12px; color: var(--site-secondary-text-color); }
.feedback-field { display: flex; flex-direction: column; gap: 10px; margin: 16px 0; line-height: 1.65; white-space: pre-wrap; }
.unknown-outcome { font-size: 13px; margin: 12px 0 0; color: var(--site-secondary-text-color); }
</style>
