<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'Mindmap',
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
    "task_name": "output.mindmap",
    "has_inputs": true,
    "template": {
      "content": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "content",
        "display_name": "content",
        "type": "str|list",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "show_mind_map": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": true,
        "password": false,
        "name": "show_mind_map",
        "display_name": "show_mind_map",
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
  <BaseNode :title="t('components.nodes.outputs.Mindmap.title')" :description="props.data.description"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">

        <a-col :span="24">
          <BaseField id="content" :name="t('components.nodes.outputs.Mindmap.content')" required type="target"
            v-model:show="fieldsData.content.show">
            <a-textarea v-model:value="fieldsData.content.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.content.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="show_mind_map" :name="t('components.nodes.outputs.Mindmap.show_mind_map')" required type="target"
            v-model:show="fieldsData.show_mind_map.show">
            <a-checkbox v-model:checked="fieldsData.show_mind_map.value">
              {{ t('components.nodes.outputs.Mindmap.show_mind_map') }}
            </a-checkbox>
          </BaseField>
        </a-col>
      </a-row>
    </template>

  </BaseNode>
</template>

<style></style>