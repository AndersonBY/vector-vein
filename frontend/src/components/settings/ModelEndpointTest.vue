<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { settingAPI } from '@/api/user'
import { useModelEndpointTest } from '@/utils/modelEndpointTest'

const props = defineProps({
  endpoint: { type: Object, default: null },
  backend: { type: String, default: 'local' },
  modelId: { type: String, default: '' },
  active: { type: Boolean, default: true },
  editableModel: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  selectBackend: { type: Boolean, default: false },
})
const { t } = useI18n()
const modelId = ref(props.modelId)
const backend = ref(props.backend)
const message = ref(props.compact ? 'Hi' : 'Hi!')
watch(() => props.modelId, value => { modelId.value = value })
watch(() => props.backend, value => { backend.value = value })
const backendOptions = computed(() => [
  { value: 'local', label: t('settings.model_test_local_backend') },
  ...['openai', 'anthropic', 'deepseek', 'qwen', 'gemini', 'moonshot', 'zhipuai', 'minimax',
    'mistral', 'yi', 'baichuan', 'groq', 'ernie', 'stepfun', 'xai'].map(value => ({ value, label: value })),
])
const { state, submit } = useModelEndpointTest(() => ({
  endpoint: props.endpoint,
  backend: props.selectBackend ? backend.value : props.backend,
  modelId: props.editableModel ? modelId.value : props.modelId,
  message: message.value,
  active: props.active,
}), settingAPI, t)
</script>

<template>
  <section class="model-endpoint-test" :class="{ compact }" :aria-label="t('settings.test_model_endpoint')">
    <a-typography-title v-if="!compact" :level="5">{{ t('settings.test_model_endpoint') }}</a-typography-title>
    <a-typography-paragraph v-if="!compact" type="secondary">{{ t('settings.model_test_tip') }}</a-typography-paragraph>
    <a-divider v-if="compact" />
    <a-form :layout="compact ? 'horizontal' : 'vertical'"
      :label-col="compact ? { span: 8 } : undefined" :wrapper-col="compact ? { span: 16 } : undefined">
      <a-form-item v-if="selectBackend" :label="t('settings.model_test_backend')">
        <a-select v-model:value="backend" :options="backendOptions" />
      </a-form-item>
      <a-form-item v-if="!compact || editableModel" :label="t('settings.model_id')">
        <a-input v-if="editableModel" v-model:value="modelId" />
        <a-typography-text v-else>{{ props.modelId }}</a-typography-text>
      </a-form-item>
      <a-form-item :label="t('settings.model_test_message')">
        <a-textarea v-model:value="message" :auto-size="{ minRows: 2, maxRows: 5 }" />
      </a-form-item>
      <a-button class="model-test-button" :loading="state.loading" :disabled="!active || state.loading" @click="submit">
        {{ t('settings.test_model_endpoint') }}
      </a-button>
    </a-form>
    <div class="model-test-result" aria-live="polite" :aria-busy="state.loading">
      <p v-if="state.error" role="alert">{{ state.error }}</p>
      <template v-if="state.completed">
        <strong>{{ t('settings.model_test_response') }}</strong>
        <pre>{{ state.content || t('settings.model_test_empty_response') }}</pre>
        <template v-if="state.reasoningContent">
          <strong>{{ t('settings.model_test_reasoning') }}</strong>
          <pre>{{ state.reasoningContent }}</pre>
        </template>
      </template>
    </div>
  </section>
</template>

<style scoped>
.model-endpoint-test { margin-top: 16px; }
.compact .model-test-button, .compact .model-test-result { margin-left: 33.333333%; }
.model-test-result { margin-top: 12px; overflow-wrap: anywhere; }
.model-test-result pre { white-space: pre-wrap; font-family: inherit; }
.model-test-result [role="alert"] { color: #cf1322; white-space: pre-wrap; }
</style>
