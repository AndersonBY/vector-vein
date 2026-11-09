<script setup>
import IconButton from '@/components/IconButton.vue'
import { Down } from '@/icons'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { interactionAnswer, interactionTarget } from '@/utils/taskAgentTimeline'
const props = defineProps({ question: { type: Object, required: true }, busy: Boolean, disabled: Boolean })
const emit = defineEmits(['answer', 'approve'])
const { t } = useI18n()
const expanded = ref(true)
const selected = ref([])
const text = ref('')
const reviewing = computed(() => props.question.permission_mode === 'auto' && (!props.question.risk_review || props.question.risk_review.status !== 'manual'))
const answer = computed(() => interactionAnswer(props.question, selected.value, text.value))
watch(() => props.question.requestDigest || props.question.requestId, () => { selected.value = []; text.value = ''; expanded.value = true })
const submit = () => { if (answer.value) emit('answer', { kind: 'respond', target: interactionTarget(props.question), answer: answer.value }) }
</script>

<template>
  <section class="interaction" :aria-label="t('workspace.taskAgentSpace.needs_answer')">
    <header class="interaction-header"><h3>{{ t(question.kind === 'user' ? 'workspace.taskAgentSpace.needs_answer' : reviewing ? 'workspace.taskAgentSpace.risk_reviewing' : 'workspace.taskAgentSpace.approval_title') }}</h3><IconButton type="text" size="small" :aria-expanded="expanded" @click="expanded = !expanded" :text="t(expanded ? 'workspace.taskAgentSpace.collapse_panel' : 'workspace.taskAgentSpace.expand_panel')"><template #icon><Down :style="{ transform: expanded ? 'rotate(180deg)' : undefined }" /></template></IconButton></header>
    <p v-if="!expanded" class="collapsed-question">{{ question.prompt || question.tool_name }}</p>
    <div v-show="expanded" class="interaction-content">
    <template v-if="question.kind === 'user'">
      <p class="question">{{ question.prompt }}</p>
      <a-radio-group v-if="question.answerSpec?.kind === 'single'" :value="selected[0]" :disabled="busy || disabled" @update:value="selected = [$event]">
        <a-radio v-for="option in question.answerSpec.options" :key="option" :value="option">{{ option }}</a-radio>
      </a-radio-group>
      <a-checkbox-group v-if="question.answerSpec?.kind === 'multi'" v-model:value="selected" :options="question.answerSpec.options" :disabled="busy || disabled" />
      <a-textarea v-model:value="text" :aria-label="t('workspace.taskAgentSpace.your_answer')" :placeholder="t('workspace.taskAgentSpace.answer_placeholder')" :auto-size="{ minRows: 2, maxRows: 5 }" :disabled="busy || disabled" @keydown.ctrl.enter.prevent="submit" />
      <a-button type="primary" :loading="busy" :disabled="!answer || disabled" @click="submit">{{ t('workspace.taskAgentSpace.submit_answer') }}</a-button>
    </template>
    <template v-else>
      <div v-if="question.risk_review" class="risk-review" role="status">
        <p>{{ t('workspace.taskAgentSpace.risk_status_' + question.risk_review.status) }} · {{ t('workspace.taskAgentSpace.risk_reason_' + (question.risk_review.reason || 'reviewing')) }}</p>
        <small v-if="question.risk_review.model">{{ t('workspace.taskAgentSpace.risk_model_label') }}：{{ question.risk_review.model_provider }} / {{ question.risk_review.model }}</small>
        <router-link v-if="['not_configured', 'review_failed'].includes(question.risk_review.reason)" :to="{ name: 'settings', query: { section: 'model_preferences' } }">{{ t('workspace.taskAgentSpace.risk_configure') }}</router-link>
      </div>
      <p>{{ question.tool_name || t('workspace.taskAgentSpace.approval_description') }}</p>
      <template v-if="question.workflow">
        <p>{{ t('workspace.taskAgentSpace.workflow_approval_scope') }}</p>
        <router-link :to="{ name: 'WorkflowUse', params: { workflowId: question.workflow.workflow_id } }">{{ t('workspace.taskAgentSpace.inspect_workflow') }} · v{{ question.workflow.version }}</router-link>
      </template>
      <pre v-if="question.arguments">{{ JSON.stringify(question.arguments, null, 2) }}</pre>
      <a-space v-if="!reviewing">
        <a-button :disabled="busy || disabled" @click="emit('approve', 'deny')">{{ t('workspace.taskAgentSpace.deny') }}</a-button>
        <a-button type="primary" :loading="busy" :disabled="disabled" @click="emit('approve', 'allow')">{{ t('workspace.taskAgentSpace.allow_once') }}</a-button>
      </a-space>
    </template>
    </div>
  </section>
</template>

<style scoped>
.interaction { padding: 12px 14px; border: var(--border-color); border-radius: 12px; background: var(--gray-background); font-size: 14px; }
.interaction-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.interaction-content { max-height: min(520px, 65vh); overflow: auto; overscroll-behavior: contain; }
.collapsed-question { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
h3 { margin: 0; font-size: 15px; font-weight: 600; }
.question { white-space: pre-wrap; line-height: 1.65; }
.interaction :deep(.ant-radio-group), .interaction :deep(.ant-checkbox-group) { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.interaction textarea { margin-bottom: 12px; }
pre { max-height: 180px; overflow: auto; white-space: pre-wrap; }
</style>
