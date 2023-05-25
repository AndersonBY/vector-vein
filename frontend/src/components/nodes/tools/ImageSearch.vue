<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'ImageSearch',
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
    "task_name": "tools.image_search",
    "has_inputs": true,
    "template": {
      "search_text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "search_text",
        "display_name": "search_text",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "search_engine": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "bing",
        "password": false,
        "options": [
          {
            "value": "bing",
            "label": "bing"
          },
          {
            "value": "pexels",
            "label": "pexels"
          }
        ],
        "name": "search_engine",
        "display_name": "search_engine",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "count": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 5,
        "password": false,
        "name": "count",
        "display_name": "count",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "output_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "markdown",
        "password": false,
        "options": [
          {
            "value": "text",
            "label": "text"
          },
          {
            "value": "markdown",
            "label": "markdown"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": [],
        "password": false,
        "name": "output",
        "display_name": "output",
        "type": "list|str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
      }
    }
  },
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)

fieldsData.value.search_engine.options = fieldsData.value.search_engine.options.map(item => {
  item.label = t(`components.nodes.tools.ImageSearch.search_engine_${item.value}`)
  return item
})
fieldsData.value.output_type.options = fieldsData.value.output_type.options.map(item => {
  item.label = t(`components.nodes.tools.ImageSearch.output_type_${item.value}`)
  return item
})

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.tools.ImageSearch.title')" :description="props.data.description"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="search_text" :name="t('components.nodes.tools.ImageSearch.search_text')" required type="target"
            v-model:show="fieldsData.search_text.show">
            <a-input class="field-content" v-model:value="fieldsData.search_text.value"
              :placeholder="fieldsData.search_text.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="search_engine" :name="t('components.nodes.tools.ImageSearch.search_engine')" required
            type="target" v-model:show="fieldsData.search_engine.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.search_engine.value"
              :options="fieldsData.search_engine.options" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="count" :name="t('components.nodes.tools.ImageSearch.count')" required type="target"
            v-model:show="fieldsData.count.show">
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.count.value"
              :placeholder="fieldsData.count.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="output_type" :name="t('components.nodes.tools.ImageSearch.output_type')" required
            type="target" v-model:show="fieldsData.output_type.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.output_type.value"
              :options="fieldsData.output_type.options" />
          </BaseField>
        </a-col>

      </a-row>
    </template>

    <template #output>
      <BaseField id="output" :name="t('components.nodes.tools.ImageSearch.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>