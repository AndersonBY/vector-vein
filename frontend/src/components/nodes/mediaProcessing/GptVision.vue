<script setup>
import { computed, onBeforeMount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import ModelSelector from '@/components/ModelSelector.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import ModelCapabilities from '@/components/ModelCapabilities.vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { hydrateTemplateModelField } from '@/utils/modelCatalog'
import { createTemplateData } from './GptVision'

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
const { t } = useI18n()
const modelCatalogStore = useModelCatalogStore()
const catalogReady = computed(() => modelCatalogStore.loaded && !modelCatalogStore.loading && !modelCatalogStore.loadError)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})

onBeforeMount(async () => {
  await hydrateTemplateModelField(fieldsData, 'OpenAI', 'llm_model', true)
})

watch(() => fieldsData.value.images_or_urls, () => {
  if (fieldsData.value.images_or_urls.value == 'images') {
    fieldsData.value.urls.show = false
  } else {
    fieldsData.value.images.show = false
  }
}, { deep: true })
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData" :data="props.data"
    translatePrefix="components.nodes.mediaProcessing.GptVision"
    documentPath="/help/docs/media-processing#node-GptVision">
    <template #field-llm_model>
      <BaseField :name="t('components.nodes.mediaProcessing.GptVision.llm_model')" :required="fieldsData.llm_model.required"
        type="target" v-model:data="fieldsData.llm_model">
        <ModelSelector v-model="fieldsData.llm_model.value" :options="fieldsData.llm_model.options"
          :loading="modelCatalogStore.loading" :ready="catalogReady" />
      </BaseField>
    </template>
    <template #afterInputs>
      <ModelCapabilities provider="OpenAI" :model="fieldsData.llm_model?.value" />
    </template>
  </BaseNode>
</template>
