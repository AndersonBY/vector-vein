<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { hasModelOption, filterModelOption } from '@/utils/modelSelection'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  loading: Boolean,
  ready: { type: Boolean, default: true },
  disabled: Boolean,
  placeholder: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const unavailable = computed(() => props.ready && !props.loading && Boolean(props.modelValue) && !hasModelOption(props.options, props.modelValue))
</script>

<template>
  <div class="model-selector">
    <a-select class="nodrag" style="width: 100%;" :value="modelValue || undefined" :options="options"
      show-search allow-clear :filter-option="filterModelOption" :loading="loading" :disabled="disabled || loading"
      :placeholder="placeholder || t('components.model_selector.select_model')" :aria-label="t('components.nodes.llms.common.llm_model')"
      :status="unavailable ? 'error' : undefined" :aria-invalid="unavailable"
      @update:value="emit('update:modelValue', $event ?? '')">
      <template #notFoundContent>
        <span>{{ t(loading ? 'components.model_selector.loading' : ready && !options.length ? 'components.model_selector.empty' : 'components.model_selector.no_match') }}</span>
      </template>
    </a-select>
    <div v-if="unavailable" class="model-selector-error" role="status">
      <a-typography-text type="danger">{{ t('components.model_selector.model_unavailable') }}</a-typography-text>
    </div>
  </div>
</template>

<style scoped>
.model-selector { min-width: 0; width: 100%; }
.model-selector-error { margin-top: 4px; font-size: 12px; line-height: 1.5; }
</style>
