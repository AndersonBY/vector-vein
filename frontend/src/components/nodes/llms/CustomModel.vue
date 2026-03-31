<script setup>
import { onBeforeMount, ref, watch } from 'vue'
import BaseLLMComponent from './_BaseLLM.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import { createTemplateData } from './CustomModel.js'
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

const refreshFamilyOptions = () => {
  fieldsData.value.model_family.options = (modelCatalogStore.modelFamilies || [])
    .filter((item) => item.isCustom)
    .map((item) => ({
      value: item.key,
      label: item.label,
    }))
  if (!fieldsData.value.model_family.value && fieldsData.value.model_family.options.length > 0) {
    fieldsData.value.model_family.value = fieldsData.value.model_family.options[0].value
  }
}

const refreshModelOptions = (family) => {
  const models = modelCatalogStore.familyMap?.[family] || []
  fieldsData.value.llm_model.options = models.map((item) => ({
    value: item.value || item.key || item.id,
    label: item.label || item.id || item.key,
  }))
  if (!fieldsData.value.llm_model.options.some((item) => item.value === fieldsData.value.llm_model.value)) {
    fieldsData.value.llm_model.value = fieldsData.value.llm_model.options[0]?.value || ''
  }
}

onBeforeMount(async () => {
  mergeTemplateIntoFields(fieldsData, createTemplateData())
  await modelCatalogStore.ensureLoaded()
  refreshFamilyOptions()
  refreshModelOptions(fieldsData.value.model_family.value)
})

watch(
  () => fieldsData.value?.model_family?.value,
  (family) => {
    refreshModelOptions(family)
  }
)
</script>

<template>
  <BaseLLMComponent :id="id" :data="props.data" :createTemplateData="createTemplateData" :debug="props.data.debug"
    v-model:templateData="fieldsData" llmName="CustomModel" :responseFormatAvailable="true"
    :functionCallAvailable="true">
    <template #modelSelection>
      <a-flex vertical gap="small">
        <BaseField name="Model Family" type="target" v-model:data="fieldsData.model_family">
          <a-select v-model:value="fieldsData.model_family.value" :options="fieldsData.model_family.options" />
        </BaseField>
        <BaseField name="Model" required type="target" v-model:data="fieldsData.llm_model">
          <a-select v-model:value="fieldsData.llm_model.value" :options="fieldsData.llm_model.options" />
        </BaseField>
      </a-flex>
    </template>
  </BaseLLMComponent>
</template>
