<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme } from 'ant-design-vue'
import { hasModelOption, filterModelOption } from '@/utils/modelSelection'

const props = defineProps({
  options: { type: Array, required: true },
  expanded: Boolean,
  loading: Boolean,
  ready: { type: Boolean, default: true },
  disabled: Boolean,
})
const model = defineModel('model', { type: String, default: '' })
const modelProvider = defineModel('modelProvider', { type: String, default: '' })
const { t } = useI18n()
const { token } = theme.useToken()
const search = ref('')
const disabled = computed(() => props.disabled || props.loading)
const options = computed(() => props.options.map(provider => ({
  ...provider,
  label: provider.labelText || provider.label || provider.value,
  children: provider.children || [],
})).filter(provider => provider.children.length))
const provider = computed(() => options.value.find(item => item.value === modelProvider.value))
const providerUnavailable = computed(() => props.ready && !props.loading && Boolean(modelProvider.value) && !hasModelOption(options.value, modelProvider.value))
const modelUnavailable = computed(() => props.ready && !props.loading && Boolean(model.value) &&
  (providerUnavailable.value || !hasModelOption(provider.value?.children || [], model.value)))
const unavailable = computed(() => providerUnavailable.value || modelUnavailable.value)
const selection = computed(() => modelProvider.value ? [modelProvider.value, model.value].filter(Boolean) : [])
const filteredOptions = computed(() => options.value.map(item => ({
  ...item,
  children: filterModelOption(search.value, item) ? item.children : item.children.filter(child => filterModelOption(search.value, child)),
})).filter(item => item.children.length))
const providerItems = computed(() => filteredOptions.value.map(item => ({ key: item.value, label: item.label, disabled: item.disabled })))
const modelItems = computed(() => (filteredOptions.value.find(item => item.value === modelProvider.value)?.children || [])
  .map(item => ({ key: item.value, label: item.label, disabled: item.disabled })))
const emptyText = computed(() => t(props.loading ? 'components.model_selector.loading' :
  props.ready && !options.value.length ? 'components.model_selector.empty' : 'components.model_selector.no_match'))

const selectProvider = ({ key }) => {
  if (disabled.value || key === modelProvider.value || !hasModelOption(options.value, key)) return
  modelProvider.value = key
  model.value = ''
}
const selectModel = ({ key }) => {
  if (disabled.value || provider.value?.disabled || !hasModelOption(provider.value?.children || [], key)) return
  model.value = key
}
const selectPair = value => {
  if (disabled.value) return
  const [providerKey = '', modelKey = ''] = value || []
  if (providerKey && (!hasModelOption(options.value, providerKey) ||
    !hasModelOption(options.value.find(item => item.value === providerKey)?.children || [], modelKey))) return
  modelProvider.value = providerKey
  model.value = modelKey
}
</script>

<template>
  <div class="model-selector" :style="{ '--selector-border': token.colorBorder, '--selector-secondary': token.colorTextSecondary }">
    <a-cascader v-if="!expanded" class="nodrag" style="width: 100%;" :value="selection" :options="options"
      :disabled="disabled" :show-search="{ filter: (input, path) => path.some(item => filterModelOption(input, item)) }"
      :placeholder="t('components.model_selector.select_model')" :aria-label="t('components.nodes.llms.common.llm_model')"
      :status="unavailable ? 'error' : undefined" :aria-invalid="unavailable" @change="selectPair">
      <template #notFoundContent>{{ emptyText }}</template>
    </a-cascader>
    <div v-else class="model-selector-expanded" :aria-busy="loading">
      <a-input v-model:value="search" class="model-search" allow-clear :disabled="disabled"
        :placeholder="t('components.model_selector.search')" :aria-label="t('components.model_selector.search')" />
      <div class="model-columns">
        <div class="provider-column">
          <a-menu mode="vertical" :selected-keys="modelProvider ? [modelProvider] : []" :items="providerItems"
            :disabled="disabled" :aria-label="t('components.model_selector.provider')" @click="selectProvider" />
          <div v-if="!providerItems.length" class="empty-models" role="status">{{ emptyText }}</div>
        </div>
        <div class="model-column">
          <a-menu mode="vertical" :selected-keys="model ? [model] : []" :items="modelItems"
            :disabled="disabled || Boolean(provider?.disabled)" :aria-label="t('components.nodes.llms.common.llm_model')" @click="selectModel" />
          <div v-if="!modelItems.length" class="empty-models" role="status">
            {{ modelProvider || loading || !options.length ? emptyText : t('components.model_selector.select_provider') }}
          </div>
        </div>
      </div>
    </div>
    <div v-if="unavailable" class="model-selector-error" role="status">
      <a-typography-text type="danger">
        {{ [modelProvider, model].filter(Boolean).join(' / ') }} ·
        {{ t(providerUnavailable ? 'components.model_selector.provider_unavailable' : 'components.model_selector.model_unavailable') }}
      </a-typography-text>
    </div>
  </div>
</template>

<style scoped>
.model-selector { min-width: 0; width: 100%; }
.model-selector-expanded { border: 1px solid var(--selector-border); border-radius: 6px; overflow: hidden; }
.model-search { border: 0; border-bottom: 1px solid var(--selector-border); border-radius: 0; }
.model-columns { display: grid; grid-template-columns: 5fr 7fr; min-height: 300px; }
.provider-column, .model-column { min-width: 0; max-height: 300px; overflow: auto; }
.provider-column { border-right: 1px solid var(--selector-border); }
.model-columns :deep(.ant-menu) { border: 0; }
.empty-models { padding: 12px; color: var(--selector-secondary); font-size: 12px; }
.model-selector-error { margin-top: 4px; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
</style>
