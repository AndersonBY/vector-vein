<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import { createTemplateData } from './TextInOut'

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

const { t } = useI18n()

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})

const showEditField = ref(false)
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.textProcessing.TextInOut"
    :debug="props.data.debug" documentLink="https://vectorvein.com/help/docs/text-processing#h2-12">
    <template #main>
      <BaseField :name="fieldsData.text.display_name" required editable @edit="showEditField = true" type="target"
        v-model:data="fieldsData.text">
        <a-textarea class="field-content" v-model:value="fieldsData.text.value"
          :placeholder="fieldsData.text.placeholder" :autoSize="{ minRows: 2, maxRows: 10 }" />
        <a-modal v-model:open="showEditField" :title="t('components.nodes.textProcessing.TextInOut.edit_name')"
          :footer="null">
          <a-input v-model:value="fieldsData.text.display_name" />
        </a-modal>
      </BaseField>
    </template>
  </BaseNode>
</template>