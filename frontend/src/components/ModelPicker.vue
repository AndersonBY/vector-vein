<script setup>
import { computed, ref, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme } from 'ant-design-vue'
import { CheckOne, Down } from '@/icons'
import ModelSelector from '@/components/ModelSelector.vue'
import { useUserSettingsStore } from '@/stores/userSettings'
import { MODEL_PREFERENCES, validModelPair, availableReasoningEfforts } from '@/utils/modelPreferences'
import { hasModelOption } from '@/utils/modelSelection'

const props = defineProps({
  options: { type: Array, required: true },
  disabled: Boolean,
  loading: Boolean,
  ready: { type: Boolean, default: true },
  saveSelection: { type: Function, default: null },
})
const model = defineModel('model', { type: String, default: '' })
const modelProvider = defineModel('modelProvider', { type: String, default: '' })
const preference = defineModel('preference', { type: String, default: 'custom' })
const reasoningEffort = defineModel('reasoningEffort', { type: String, default: 'default' })
const { t } = useI18n()
const { token } = theme.useToken()
const settings = useUserSettingsStore()
const preferences = computed(() => settings.setting.data?.model_preferences || {})
const dropdownOpen = ref(false)
const modalOpen = ref(false)
const draftProvider = ref('')
const draftModel = ref('')
const saving = ref(false)
const failed = ref(false)
const disabled = computed(() => props.disabled || props.loading || saving.value)
const validDraft = computed(() => validModelPair(props.options, draftProvider.value, draftModel.value))
const unavailable = computed(() => props.ready && !props.loading && (
  (Boolean(model.value) && !validModelPair(props.options, modelProvider.value, model.value)) ||
  (Boolean(modelProvider.value) && !hasModelOption(props.options, modelProvider.value))
))
const selectedPreference = computed(() => {
  const preset = preferences.value[preference.value]
  return preset && preset.model_provider === modelProvider.value && preset.model === model.value ? preference.value : 'custom'
})
const modelLabel = (provider, value) => props.options.find(item => item.value === provider)?.children?.find(item => item.value === value)?.label || value
const presetValid = key => validModelPair(props.options, preferences.value[key]?.model_provider, preferences.value[key]?.model)
const presetDescription = key => presetValid(key) ? modelLabel(preferences.value[key].model_provider, preferences.value[key].model) : t('components.model_picker.not_configured')
const effortOptions = computed(() => availableReasoningEfforts(settings.setting.data?.llm_settings?.backends, modelProvider.value, model.value))
const sliderIndex = ref(null)
const effortIndex = computed(() => Math.max(0, effortOptions.value.indexOf(reasoningEffort.value)))
const effortMarks = computed(() => Object.fromEntries(effortOptions.value.map((_, index) => [index, ''])))
const effortLabel = computed(() => t(`components.model_picker.effort_${reasoningEffort.value}`))
const selectedLabel = computed(() => modelLabel(modelProvider.value, model.value) || t('components.model_selector.select_model'))
let generation = 0
onBeforeUnmount(() => { generation++ })

const commit = async (selection, close = true) => {
  if (disabled.value || !validModelPair(props.options, selection.model_provider, selection.model)) return
  const version = ++generation
  saving.value = true
  failed.value = false
  try {
    if (props.saveSelection && await props.saveSelection(selection) === false) return
    if (version !== generation) return
    modelProvider.value = selection.model_provider
    model.value = selection.model
    preference.value = selection.model_preference
    reasoningEffort.value = selection.reasoning_effort
    if (close) { modalOpen.value = false; dropdownOpen.value = false }
  } catch {
    if (version === generation) failed.value = true
  } finally {
    if (version === generation) saving.value = false
  }
}
const selection = (provider, value, preset = 'custom') => ({
  model_provider: provider, model: value, model_preference: preset,
  reasoning_effort: availableReasoningEfforts(settings.setting.data?.llm_settings?.backends, provider, value).includes(reasoningEffort.value) ? reasoningEffort.value : 'default',
})
const menuClick = ({ key }) => {
  if (disabled.value) return
  if (key === 'custom') {
    draftProvider.value = modelProvider.value
    draftModel.value = model.value
    failed.value = false
    dropdownOpen.value = false
    modalOpen.value = true
  } else if (presetValid(key)) {
    const preset = preferences.value[key]
    commit(selection(preset.model_provider, preset.model, key))
  }
}
const confirm = () => commit(selection(draftProvider.value, draftModel.value))
const cancel = () => { if (!saving.value) { modalOpen.value = false; failed.value = false } }
const effortChanged = index => {
  const effort = effortOptions.value[index]
  if (effort) commit({ ...selection(modelProvider.value, model.value, selectedPreference.value), reasoning_effort: effort }, false)
}
</script>

<template>
  <div class="model-picker nodrag nowheel" :style="{
    '--picker-text': token.colorText, '--picker-secondary': token.colorTextSecondary,
    '--picker-hover': token.colorFillTertiary, '--picker-border': token.colorBorderSecondary,
  }">
    <a-dropdown v-model:open="dropdownOpen" :trigger="['click']" placement="topRight" :disabled="disabled">
      <button type="button" class="selected-model-tag" :disabled="disabled" :aria-expanded="dropdownOpen" aria-haspopup="menu"
        :aria-label="t('components.model_picker.title')" :title="`${selectedLabel} · ${effortLabel}`">
        <span class="selected-model-name">{{ selectedLabel }}</span>
        <span class="selected-model-effort">{{ effortLabel }}</span>
        <Down :size="12" aria-hidden="true" />
      </button>
      <template #overlay>
        <a-menu :selected-keys="[selectedPreference]" @click="menuClick" class="model-preference-menu">
          <a-menu-item v-for="key in MODEL_PREFERENCES" :key="key" :disabled="disabled || !presetValid(key)">
            <div class="preference-item">
              <div><div>{{ t(`components.model_picker.${key}`) }}</div><small>{{ presetDescription(key) }}</small></div>
              <CheckOne v-if="selectedPreference === key" :size="16" aria-hidden="true" />
            </div>
          </a-menu-item>
          <a-menu-item key="custom" :disabled="disabled">
            <div class="preference-item">
              <div><div>{{ t('components.model_picker.custom') }}</div><small>{{ t('components.model_picker.custom_description') }}</small></div>
              <CheckOne v-if="selectedPreference === 'custom'" :size="16" aria-hidden="true" />
            </div>
          </a-menu-item>
          <a-menu-divider />
          <a-menu-item key="reasoning" class="reasoning-item">
            <div @click.stop>
              <div class="reasoning-header"><span>{{ t('components.model_picker.reasoning') }}</span><span>{{ effortLabel }}</span></div>
              <a-slider :value="sliderIndex ?? effortIndex" :disabled="disabled || !validModelPair(options, modelProvider, model) || effortOptions.length < 2"
                :min="0" :max="Math.max(1, effortOptions.length - 1)" :step="1" :marks="effortMarks" :tooltip-open="false"
                :aria-label="t('components.model_picker.reasoning')" @update:value="sliderIndex = $event" @after-change="index => { effortChanged(index); sliderIndex = null }" />
            </div>
          </a-menu-item>
        </a-menu>
      </template>
    </a-dropdown>
    <div v-if="unavailable" class="picker-error" role="status">
      <a-typography-text type="danger">{{ modelProvider }} / {{ model }} · {{ t('components.model_selector.model_unavailable') }}</a-typography-text>
    </div>
    <a-typography-text v-if="failed && !modalOpen" type="danger" role="alert">{{ t('components.model_selector.save_failed') }}</a-typography-text>
    <a-modal :open="modalOpen" :title="t('components.model_picker.custom')" :width="800" @ok="confirm" @cancel="cancel"
      :confirm-loading="saving" :ok-button-props="{ disabled: !validDraft || disabled }" :cancel-button-props="{ disabled: saving }"
      :closable="!saving" :mask-closable="!saving" :keyboard="!saving">
      <ModelSelector v-if="modalOpen" v-model:model="draftModel" v-model:model-provider="draftProvider"
        :options="options" expanded :disabled="disabled" :loading="loading" :ready="ready" />
      <a-typography-text v-if="failed" type="danger" role="alert">{{ t('components.model_selector.save_failed') }}</a-typography-text>
    </a-modal>
  </div>
</template>

<style scoped>
.model-picker { min-width: 0; }
.selected-model-tag { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; height: 30px; padding: 0 10px; border: 0; border-radius: 999px; background: transparent; color: var(--picker-text); font: inherit; font-size: 12px; cursor: pointer; }
.selected-model-tag:hover:not(:disabled) { background: var(--picker-hover); }
.selected-model-tag:disabled { cursor: default; opacity: .5; }
.selected-model-tag:focus-visible { outline: 2px solid #28c5e5; outline-offset: 2px; }
.selected-model-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.selected-model-effort { color: var(--picker-secondary); flex-shrink: 0; }
.model-preference-menu { min-width: 220px; max-width: 320px; }
.preference-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 4px 0; }
.preference-item small { display: block; color: inherit; opacity: .55; font-size: 12px; white-space: normal; }
.reasoning-item { cursor: default; }
.reasoning-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 13px; }
.picker-error { font-size: 12px; margin-top: 4px; overflow-wrap: anywhere; }
</style>
