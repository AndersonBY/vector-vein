<script setup>
import { computed, onBeforeMount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import ModelSelector from '@/components/ModelSelector.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './Claude'
import { hydrateTemplateModelField, mergeTemplateIntoFields } from '@/utils/modelCatalog'

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
onBeforeMount(async () => {
  mergeTemplateIntoFields(fieldsData, createTemplateData())
  await hydrateTemplateModelField(fieldsData, 'Anthropic')
})
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.llms.Claude" documentPath="/help/docs/language-models#node-Claude">
    <template #field-llm_model>
      <BaseField :name="t('components.nodes.llms.common.llm_model')" :required="fieldsData.llm_model.required"
        type="target" v-model:data="fieldsData.llm_model">
        <ModelSelector v-model="fieldsData.llm_model.value" :options="fieldsData.llm_model.options"
          :loading="modelCatalogStore.loading" :ready="catalogReady" />
      </BaseField>
    </template>
  </BaseNode>
</template>
