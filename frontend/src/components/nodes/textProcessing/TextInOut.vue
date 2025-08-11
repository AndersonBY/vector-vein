<script setup>
import { ref, watch } from 'vue'
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

watch(() => fieldsData.value.input_type.value, (value) => {
  if (value == 'text') {
    fieldsData.value.text.field_type = 'textarea'
  } else if (value == 'number') {
    fieldsData.value.text.field_type = 'number'
  }
})
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" :data="props.data"
    translatePrefix="components.nodes.textProcessing.TextInOut" :debug="props.data.debug"
    documentPath="/help/docs/text-processing#node-TextInOut">
    <template #main>
      <BaseField :name="fieldsData.text.display_name" required editable @edit="showEditField = true" type="target"
        v-model:data="fieldsData.text">
        <a-textarea v-if="fieldsData.input_type.value == 'text'" class="nodrag" v-model:value="fieldsData.text.value"
          :placeholder="fieldsData.text.placeholder" :autoSize="{ minRows: 2, maxRows: 10 }" />
        <a-input-number v-if="fieldsData.input_type.value == 'number'" class="nodrag"
          v-model:value="fieldsData.text.value" style="width: 100%;" />
        <a-modal v-model:open="showEditField" :title="t('components.nodes.textProcessing.TextInOut.edit_name')"
          :footer="null">
          <a-input v-model:value="fieldsData.text.display_name" />
        </a-modal>
      </BaseField>
      <BaseField :name="t('components.nodes.textProcessing.TextInOut.input_type')" required type="target"
        v-model:data="fieldsData.input_type">
        <a-select v-model:value="fieldsData.input_type.value" :options="fieldsData.input_type.options"
          style="width: 100%;" />
      </BaseField>
    </template>
  </BaseNode>
</template>