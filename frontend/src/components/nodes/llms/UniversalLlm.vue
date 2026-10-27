<script setup>
import { computed, onBeforeMount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useVueFlow } from '@vue-flow/core'
import ModelPicker from '@/components/ModelPicker.vue'
import BaseLLMComponent from './_BaseLLM.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import { createTemplateData } from './UniversalLlm.js'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import { mergeTemplateIntoFields } from '@/utils/modelCatalog'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
})

const fieldsData = ref(props.data.template)
const modelCatalogStore = useModelCatalogStore()
const { t } = useI18n()
const { edges } = useVueFlow()
const showProviderField = computed(() => {
  const field = fieldsData.value.model_provider
  const handle = field?.id || field?.name || 'model_provider'
  return field?.show || edges.value.some(edge =>
    (edge.source === props.id && edge.sourceHandle === handle) ||
    (edge.target === props.id && edge.targetHandle === handle))
})
const catalogReady = computed(() => modelCatalogStore.loaded && !modelCatalogStore.loading && !modelCatalogStore.loadError)

const providerOptions = computed(() => (modelCatalogStore.generalModelOptions || []).map((provider) => ({
  value: provider.value,
  label: provider.label,
})))

const modelOptions = computed(() => {
  const providerEntry = (modelCatalogStore.generalModelOptions || []).find((item) => item.value === fieldsData.value.model_provider?.value)
  return (providerEntry?.children || []).map((item) => ({
    value: item.value,
    label: item.label,
  }))
})

onBeforeMount(async () => {
  mergeTemplateIntoFields(fieldsData, createTemplateData())
  await modelCatalogStore.ensureLoaded()
  fieldsData.value.model_provider.options = providerOptions
  fieldsData.value.llm_model.options = modelOptions
})
</script>

<template>
  <BaseLLMComponent :id="id" :data="props.data" :createTemplateData="createTemplateData" :debug="props.data.debug"
    v-model:templateData="fieldsData" llmName="UniversalLlm" :responseFormatAvailable="true"
    :functionCallAvailable="true">
    <template #modelSelection>
      <a-flex vertical gap="small">
        <BaseField v-if="showProviderField" :name="t('components.model_selector.provider')" type="target" v-model:data="fieldsData.model_provider">
          <a-typography-text>{{ fieldsData.model_provider.value }}</a-typography-text>
        </BaseField>
        <BaseField class="inline-model-field" :name="t('components.nodes.llms.common.llm_model')" required type="target" v-model:data="fieldsData.llm_model">
          <template #inline>
            <ModelPicker class="inline-model-picker" v-model:model="fieldsData.llm_model.value" v-model:model-provider="fieldsData.model_provider.value"
              v-model:preference="fieldsData.model_preference.value" v-model:reasoning-effort="fieldsData.reasoning_effort.value"
              :options="modelCatalogStore.generalModelOptions"
              :loading="modelCatalogStore.loading" :ready="catalogReady" />
          </template>
        </BaseField>
      </a-flex>
    </template>
  </BaseLLMComponent>
</template>

<style scoped>
.inline-model-picker { margin-left: auto; max-width: calc(100% - 84px); }
.inline-model-field :deep(.show-in-use-interface-checkbox) { flex-grow: 0; }
</style>
