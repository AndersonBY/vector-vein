<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import EmbeddingTabsSettings from './EmbeddingTabsSettings.vue'
import { rerankOptions } from './retrievalSettings'

const props = defineProps({ endpoints: { type: Array, required: true } })
const backends = defineModel('backends', { required: true })
const selection = defineModel('selection', { required: true })
const { t } = useI18n()
const options = computed(() => rerankOptions(backends.value))
const selected = computed({
  get: () => selection.value?.provider && selection.value?.model ? [selection.value.provider, selection.value.model] : [],
  set: value => { selection.value = { provider: value?.[0] || '', model: value?.[1] || '' } },
})
</script>

<template>
  <a-flex vertical gap="middle">
    <p>{{ t('settings.rerank_tip') }}</p>
    <a-form layout="vertical">
      <a-form-item :label="t('settings.rerank_default')" :extra="t('settings.rerank_selection_tip')">
        <a-cascader v-model:value="selected" :options="options" :placeholder="t('settings.rerank_off')" allow-clear />
      </a-form-item>
    </a-form>
    <EmbeddingTabsSettings v-model="backends" kind="rerank" :endpoints="props.endpoints" />
  </a-flex>
</template>
