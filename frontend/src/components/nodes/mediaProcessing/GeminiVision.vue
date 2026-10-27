<script setup>
import { computed, onBeforeMount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import ModelSelect from '@/components/ModelSelect.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import ModelCapabilities from '@/components/ModelCapabilities.vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { hydrateTemplateModelField } from '@/utils/modelCatalog'
import { createTemplateData } from './GeminiVision'

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
  await hydrateTemplateModelField(fieldsData, 'Gemini', 'llm_model', true)
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
    translatePrefix="components.nodes.mediaProcessing.GeminiVision"
    documentPath="/help/docs/media-processing#node-GeminiVision">
    <template #field-llm_model>
      <BaseField :name="t('components.nodes.mediaProcessing.GeminiVision.llm_model')" :required="fieldsData.llm_model.required"
        type="target" v-model:data="fieldsData.llm_model">
        <ModelSelect v-model="fieldsData.llm_model.value" :options="fieldsData.llm_model.options"
          :loading="modelCatalogStore.loading" :ready="catalogReady" />
      </BaseField>
    </template>
    <template #afterInputs>
      <ModelCapabilities style="margin: 8px 12px 0;" provider="Gemini" :model="fieldsData.llm_model?.value" />
    </template>
  </BaseNode>
</template>
