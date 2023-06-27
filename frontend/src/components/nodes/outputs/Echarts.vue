<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'Echarts',
})

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  events: {
    required: false,
  },
  templateData: {
    "description": "description",
    "task_name": "output.echarts",
    "has_inputs": true,
    "template": {
      "option": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "option",
        "display_name": "option",
        "type": "str|list",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "show_echarts": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": true,
        "password": false,
        "name": "show_echarts",
        "display_name": "show_echarts",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox"
      },
    }
  },
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.outputs.Echarts.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/outputs#h2-27" @delete="deleteNode">
    <template #main>
      <a-row type="flex">

        <a-col :span="24">
          <BaseField id="option" :name="t('components.nodes.outputs.Echarts.option')" required type="target"
            v-model:show="fieldsData.option.show">
            <a-textarea v-model:value="fieldsData.option.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.option.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="show_echarts" :name="t('components.nodes.outputs.Echarts.show_echarts')" required type="target"
            v-model:show="fieldsData.show_echarts.show">
            <a-checkbox v-model:checked="fieldsData.show_echarts.value">
              {{ t('components.nodes.outputs.Echarts.show_echarts') }}
            </a-checkbox>
          </BaseField>
        </a-col>
      </a-row>
    </template>

  </BaseNode>
</template>

<style></style>