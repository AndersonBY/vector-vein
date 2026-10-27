<script setup>
import { ref, computed, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import ModelSelect from '@/components/ModelSelect.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import ModelCapabilities from '@/components/ModelCapabilities.vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './LocalLlm'

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
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})

const { t } = useI18n()
const modelCatalogStore = useModelCatalogStore()
onBeforeMount(() => modelCatalogStore.ensureLoaded())
const catalogReady = computed(() => modelCatalogStore.loaded && !modelCatalogStore.loading && !modelCatalogStore.loadError)
const familyOptions = computed(() => (modelCatalogStore.modelFamilies || [])
  .filter((family) => family.isCustom)
  .map((family) => ({ value: family.key, label: family.label })))
const modelOptions = computed(() => {
  const modelFamily = fieldsData.value.model_family.value
  const models = modelCatalogStore.familyMap[modelFamily]
  return models ? models.map((model) => ({
    value: model.key,
    label: model.id || model.key,
  })) : []
})
fieldsData.value.model_family.options = familyOptions
fieldsData.value.llm_model.options = modelOptions
const familyUnavailable = computed(() => catalogReady.value && fieldsData.value.model_family.value &&
  !familyOptions.value.some((item) => item.value === fieldsData.value.model_family.value))
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.llms.LocalLlm">
    <template #field-model_family>
      <BaseField :name="t('components.model_selector.family')" type="target" v-model:data="fieldsData.model_family">
        <a-select class="nodrag" style="width: 100%;" v-model:value="fieldsData.model_family.value" :options="familyOptions"
          show-search option-filter-prop="label" @change="fieldsData.llm_model.value = ''" />
        <small v-if="familyUnavailable" role="status">{{ t('components.model_selector.family_unavailable') }}</small>
      </BaseField>
    </template>
    <template #field-llm_model>
      <BaseField :name="t('components.nodes.llms.common.llm_model')" type="target" v-model:data="fieldsData.llm_model">
        <ModelSelect v-model="fieldsData.llm_model.value" :options="modelOptions"
          :loading="modelCatalogStore.loading" :ready="catalogReady" />
      </BaseField>
    </template>
    <template #afterInputs>
      <ModelCapabilities style="margin: 8px 12px 0;" provider="local" :model="fieldsData.llm_model?.value" />
    </template>
  </BaseNode>
</template>
