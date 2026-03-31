<script setup>
import { computed, onBeforeMount, ref, watch } from 'vue'
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

const providerOptions = computed(() => (modelCatalogStore.generalModelOptions || []).map((provider) => ({
  value: provider.value,
  label: provider.label,
})))

const refreshModelOptions = (provider) => {
  const providerEntry = (modelCatalogStore.generalModelOptions || []).find((item) => item.value === provider)
  fieldsData.value.llm_model.options = (providerEntry?.children || []).map((item) => ({
    value: item.value,
    label: item.label,
  }))
  if (!fieldsData.value.llm_model.options.some((item) => item.value === fieldsData.value.llm_model.value)) {
    fieldsData.value.llm_model.value = fieldsData.value.llm_model.options[0]?.value || ''
  }
}

onBeforeMount(async () => {
  mergeTemplateIntoFields(fieldsData, createTemplateData())
  await modelCatalogStore.ensureLoaded()
  fieldsData.value.model_provider.options = providerOptions.value
  if (!fieldsData.value.model_provider.value && providerOptions.value.length > 0) {
    fieldsData.value.model_provider.value = providerOptions.value[0].value
  }
  refreshModelOptions(fieldsData.value.model_provider.value)
})

watch(
  () => fieldsData.value?.model_provider?.value,
  (provider) => {
    fieldsData.value.model_provider.options = providerOptions.value
    refreshModelOptions(provider)
  }
)
</script>

<template>
  <BaseLLMComponent :id="id" :data="props.data" :createTemplateData="createTemplateData" :debug="props.data.debug"
    v-model:templateData="fieldsData" llmName="UniversalLlm" :responseFormatAvailable="true"
    :functionCallAvailable="true">
    <template #modelSelection>
      <a-flex vertical gap="small">
        <BaseField name="Provider" type="target" v-model:data="fieldsData.model_provider">
          <a-select v-model:value="fieldsData.model_provider.value" :options="fieldsData.model_provider.options" />
        </BaseField>
        <BaseField name="Model" required type="target" v-model:data="fieldsData.llm_model">
          <a-select v-model:value="fieldsData.llm_model.value" :options="fieldsData.llm_model.options" />
        </BaseField>
      </a-flex>
    </template>
  </BaseLLMComponent>
</template>
