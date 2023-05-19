<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'TextCrawler',
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
    "task_name": "web_crawlers.text_crawler",
    "has_inputs": true,
    "template": {
      "url": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "url",
        "display_name": "url",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "output_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "text",
        "password": false,
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "output_text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output_text",
        "display_name": "output_text",
        "type": "str|dict",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "output_title": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output_title",
        "display_name": "output_title",
        "type": "str|dict",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
    }
  },
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)

fieldsData.value.output_type.options = fieldsData.value.output_type.options.map(item => {
  item.label = t(`components.nodes.webCrawlers.TextCrawler.${item.value}`)
  return item
})

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.webCrawlers.TextCrawler.title')" :description="props.data.description"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="url" :name="t('components.nodes.webCrawlers.TextCrawler.url')" required type="target">
            <a-input v-model:value="fieldsData.url.value" placeholder="https://example.com" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_type" :name="t('components.nodes.webCrawlers.TextCrawler.output_type')" required
            type="target" v-model:show="fieldsData.output_type.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.output_type.value"
              :options="fieldsData.output_type.options" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <a-row type="flex" style="width: 100%;">
        <a-col :span="24">
          <BaseField id="output_title" :name="t('components.nodes.webCrawlers.TextCrawler.output_title')" type="source"
            nameOnly>
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_text" :name="t('components.nodes.webCrawlers.TextCrawler.output_text')" type="source"
            nameOnly>
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>