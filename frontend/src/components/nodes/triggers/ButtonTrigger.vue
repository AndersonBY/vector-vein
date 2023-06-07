<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'ButtonTrigger',
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
    "task_name": "triggers.button_trigger",
    "has_inputs": false,
    "template": {
      "button_text": {
        "required": true,
        "placeholder": "Run",
        "show": false,
        "multiline": true,
        "value": "run",
        "password": false,
        "name": "button_text",
        "display_name": "button_text",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "button"
      },
    }
  },
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)
fieldsData.value.button_text.value = t('components.nodes.triggers.ButtonTrigger.run')

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.triggers.ButtonTrigger.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/triggers#h2-0" @delete="deleteNode">
    <template #main>
      <a-row type=" flex">
        <a-col :span="24">
          <BaseField id="button_text" :name="t('components.nodes.triggers.ButtonTrigger.button_text')" required
            type="target">
            <a-input class="field-content" v-model:value="fieldsData.button_text.value"
              :placeholder="fieldsData.button_text.placeholder" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>