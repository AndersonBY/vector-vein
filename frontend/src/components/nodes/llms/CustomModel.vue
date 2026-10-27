<script setup>
import { computed, onBeforeMount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ModelSelector from '@/components/ModelSelector.vue'
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
const { t } = useI18n()
const catalogReady = computed(() => modelCatalogStore.loaded && !modelCatalogStore.loading && !modelCatalogStore.loadError)

const familyOptions = computed(() => (modelCatalogStore.modelFamilies || [])
    .filter((item) => item.isCustom)
    .map((item) => ({
      value: item.key,
      label: item.label,
    })))

const modelOptions = computed(() => {
  const models = modelCatalogStore.familyMap?.[fieldsData.value.model_family?.value] || []
  return models.map((item) => ({
    value: item.value || item.key || item.id,
    label: item.label || item.id || item.key,
  }))
})
const familyUnavailable = computed(() => catalogReady.value && fieldsData.value.model_family?.value &&
  !familyOptions.value.some((item) => item.value === fieldsData.value.model_family.value))

onBeforeMount(async () => {
  mergeTemplateIntoFields(fieldsData, createTemplateData())
  await modelCatalogStore.ensureLoaded()
  fieldsData.value.model_family.options = familyOptions
  fieldsData.value.llm_model.options = modelOptions
})
</script>

<template>
  <BaseLLMComponent :id="id" :data="props.data" :createTemplateData="createTemplateData" :debug="props.data.debug"
    v-model:templateData="fieldsData" llmName="CustomModel" :responseFormatAvailable="true"
    :functionCallAvailable="true">
    <template #modelSelection>
      <a-flex vertical gap="small">
        <BaseField :name="t('components.model_selector.family')" type="target" v-model:data="fieldsData.model_family">
          <a-select class="nodrag" style="width: 100%;" v-model:value="fieldsData.model_family.value" :options="familyOptions"
            show-search option-filter-prop="label" @change="fieldsData.llm_model.value = ''" />
          <small v-if="familyUnavailable" role="status">{{ t('components.model_selector.family_unavailable') }}</small>
        </BaseField>
        <BaseField :name="t('components.nodes.llms.common.llm_model')" required type="target" v-model:data="fieldsData.llm_model">
          <ModelSelector v-model="fieldsData.llm_model.value" :options="modelOptions"
            :loading="modelCatalogStore.loading" :ready="catalogReady" />
        </BaseField>
      </a-flex>
    </template>
  </BaseLLMComponent>
</template>
