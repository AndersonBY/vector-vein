<script setup>
import { Undo } from '@/icons'
import IconButton from '@/components/IconButton.vue'
import { useI18n } from 'vue-i18n'
import ModelPicker from '@/components/ModelPicker.vue'
import { MODEL_PREFERENCES } from '@/utils/modelPreferences'
defineProps({ options: { type: Array, required: true }, backends: { type: Object, default: () => ({}) } })
const preferences = defineModel({ type: Object, required: true })
const { t } = useI18n()
const savePreset = (key, selection) => {
  preferences.value = { ...preferences.value, [key]: {
    model_provider: selection.model_provider, model: selection.model, reasoning_effort: selection.reasoning_effort,
  } }
}
</script>
<template>
  <p>{{ t('components.model_picker.preferences_help') }}</p>
  <a-form layout="vertical">
    <a-form-item v-for="key in MODEL_PREFERENCES" :key="key" :label="t(`components.model_picker.${key}`)">
      <div class="preset-selection">
        <ModelPicker :model-provider="preferences[key]?.model_provider || ''" :model="preferences[key]?.model || ''"
          :preference="key" :reasoning-effort="preferences[key]?.reasoning_effort || 'default'"
          :options="options" :presets="preferences" :backends="backends" :save-selection="selection => savePreset(key, selection)" />
        <IconButton :text="t('common.reset')" v-if="preferences[key]?.model_provider || preferences[key]?.model"
          @click="savePreset(key, { model_provider: '', model: '', reasoning_effort: 'default' })"><template #icon><Undo /></template></IconButton>
      </div>
    </a-form-item>
  </a-form>
</template>
<style scoped>
.preset-selection { display: flex; align-items: flex-start; gap: 8px; }
.preset-selection > .model-picker { min-width: 0; }
.preset-selection > .ant-btn { flex-shrink: 0; }
</style>
