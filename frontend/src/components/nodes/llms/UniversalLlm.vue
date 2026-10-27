<script setup>
import { computed, onBeforeMount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ModelSelector from '@/components/ModelSelector.vue'
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
const providerUnavailable = computed(() => catalogReady.value && fieldsData.value.model_provider?.value &&
  !providerOptions.value.some((item) => item.value === fieldsData.value.model_provider.value))

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
        <BaseField :name="t('components.model_selector.provider')" type="target" v-model:data="fieldsData.model_provider">
          <a-select class="nodrag" style="width: 100%;" v-model:value="fieldsData.model_provider.value" :options="providerOptions"
            show-search option-filter-prop="label" @change="fieldsData.llm_model.value = ''" />
          <small v-if="providerUnavailable" role="status">{{ t('components.model_selector.provider_unavailable') }}</small>
        </BaseField>
        <BaseField :name="t('components.nodes.llms.common.llm_model')" required type="target" v-model:data="fieldsData.llm_model">
          <ModelSelector v-model="fieldsData.llm_model.value" :options="modelOptions"
            :loading="modelCatalogStore.loading" :ready="catalogReady" />
        </BaseField>
      </a-flex>
    </template>
  </BaseLLMComponent>
</template>
