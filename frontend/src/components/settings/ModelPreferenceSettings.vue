<script setup>
import { useI18n } from 'vue-i18n'
import { MODEL_PREFERENCES, validModelPair } from '@/utils/modelPreferences'
const props = defineProps({ options: { type: Array, required: true } })
const preferences = defineModel({ type: Object, required: true })
const { t } = useI18n()
</script>
<template>
  <p>{{ t('components.model_picker.preferences_help') }}</p>
  <a-form layout="vertical">
    <a-form-item v-for="key in MODEL_PREFERENCES" :key="key" :label="t(`components.model_picker.${key}`)">
      <a-cascader :value="preferences[key]?.model_provider ? [preferences[key].model_provider, preferences[key].model].filter(Boolean) : []"
        :options="options" style="width: 100%;" :show-search="true" allow-clear
        @change="value => preferences[key] = { model_provider: value?.[0] || '', model: value?.[1] || '' }" />
      <a-typography-text v-if="preferences[key]?.model_provider && !validModelPair(options, preferences[key].model_provider, preferences[key].model)" type="danger">
        {{ t('components.model_selector.model_unavailable') }}
      </a-typography-text>
    </a-form-item>
  </a-form>
</template>
