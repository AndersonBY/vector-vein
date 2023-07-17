<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'

defineComponent({
  name: 'ChatGLM',
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
    "task_name": "llms.chat_glm",
    "has_inputs": true,
    "template": {
      "prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "prompt",
        "display_name": "prompt",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "llm_model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "chatglm-6b",
        "password": false,
        "options": [
          {
            "value": "chatglm-6b",
            "label": "ChatGLM-6B"
          },
        ],
        "name": "llm_model",
        "display_name": "llm_model",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "temperature": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 0.7,
        "password": false,
        "name": "temperature",
        "display_name": "temperature",
        "type": "float",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output",
        "display_name": "output",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
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
  <BaseNode :title="t('components.nodes.llms.ChatGLM.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/language-models#h2-4" @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="prompt" :name="t('components.nodes.llms.ChatGLM.prompt')" required type="target"
            v-model:show="fieldsData.prompt.show">
            <a-textarea class="field-content" v-model:value="fieldsData.prompt.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.prompt.placeholder" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="llm_model" :name="t('components.nodes.llms.ChatGLM.llm_model')" required type="target"
            v-model:show="fieldsData.llm_model.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.llm_model.value"
              :options="fieldsData.llm_model.options" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="temperature" :name="t('components.nodes.llms.ChatGLM.temperature')" required type="target"
            v-model:show="fieldsData.temperature.show">
            <TemperatureInput v-model="fieldsData.temperature.value" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.llms.ChatGLM.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>