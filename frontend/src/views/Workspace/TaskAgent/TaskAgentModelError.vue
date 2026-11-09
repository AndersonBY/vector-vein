<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { modelFailureCategory, modelHttpStatus } from '@/utils/taskAgentErrors'
const props = defineProps({ failure: { type: Object, required: true }, modelConfig: { type: Object, default: () => ({}) } })
const { t } = useI18n()
const category = computed(() => modelFailureCategory(props.failure))
const httpStatus = computed(() => modelHttpStatus(props.failure))
const title = computed(() => {
  const text = t('workspace.taskAgentSpace.model_error_' + category.value + '_title')
  return httpStatus.value ? t('workspace.taskAgentSpace.model_error_with_http', { title: text, status: httpStatus.value }) : text
})
</script>
<template>
  <a-alert type="error" show-icon class="model-error" :message="title">
    <template #description>
      <p>{{ t('workspace.taskAgentSpace.model_error_' + category + '_hint') }}</p>
      <p v-if="failure.parameter">{{ t('workspace.taskAgentSpace.model_error_parameter_name', { name: failure.parameter }) }}</p>
      <router-link :to="{ name: 'settings' }">{{ t('workspace.taskAgentSpace.check_model_settings') }}</router-link>
      <details>
        <summary>{{ t('workspace.taskAgentSpace.error_details') }}</summary>
        <dl>
          <template v-if="httpStatus"><dt>HTTP</dt><dd>{{ httpStatus }}</dd></template>
          <template v-if="modelConfig.selected_model"><dt>{{ t('workspace.taskAgentSpace.configured_model') }}</dt><dd>{{ modelConfig.selected_model }}</dd></template>
          <template v-if="modelConfig.model_id"><dt>{{ t('workspace.taskAgentSpace.request_model') }}</dt><dd>{{ modelConfig.model_id }}</dd></template>
        </dl>
        <p>{{ t('workspace.taskAgentSpace.model_config_snapshot_hint') }}</p>
        <p v-if="!failure.response_rejected && !['configuration', 'credentials_missing', 'reasoning'].includes(category)">{{ t('workspace.taskAgentSpace.model_outcome_hint') }}</p>
      </details>
    </template>
  </a-alert>
</template>
<style scoped>
.model-error p { margin: 0 0 10px; line-height: 1.65; }
details { margin-top: 12px; font-size: 13px; }
summary { cursor: pointer; color: var(--site-secondary-text-color); }
summary:focus-visible { outline: 2px solid var(--color-primary); }
dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 5px 12px; margin: 12px 0; }
dt { color: var(--site-secondary-text-color); }
dd { margin: 0; overflow-wrap: anywhere; }
</style>
