<script setup>
import { useI18n } from 'vue-i18n'
import { validModelPair } from '@/utils/modelPreferences'
const props = defineProps({ options: { type: Array, required: true } })
const selection = defineModel({ type: Object, required: true })
const { t } = useI18n()
</script>
<template>
  <section id="task-agent-approval">
    <h3>{{ t('workspace.taskAgentSpace.risk_model_title') }}</h3>
    <p>{{ t('workspace.taskAgentSpace.risk_model_help') }}</p>
    <a-form layout="vertical">
      <a-form-item :label="t('workspace.taskAgentSpace.risk_model_label')">
        <a-cascader :value="selection.model_provider ? [selection.model_provider, selection.model].filter(Boolean) : []" :options="props.options" :show-search="true" allow-clear style="width: 100%" :placeholder="t('workspace.taskAgentSpace.risk_model_unset')" :aria-label="t('workspace.taskAgentSpace.risk_model_label')" @change="value => selection = { model_provider: value?.[0] || '', model: value?.[1] || '' }" />
        <a-typography-text v-if="selection.model_provider && !validModelPair(props.options, selection.model_provider, selection.model)" type="danger">{{ t('components.model_selector.model_unavailable') }}</a-typography-text>
      </a-form-item>
    </a-form>
  </section>
</template>
<style scoped>
section { margin-top: 24px; padding-top: 20px; border-top: var(--light-border); }
h3 { font-size: 16px; font-weight: 500; }
p { color: var(--site-secondary-text-color); line-height: 1.65; }
</style>
