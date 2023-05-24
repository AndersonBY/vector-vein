<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'BilibiliCrawler',
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
    "task_name": "web_crawlers.bilibili_crawler",
    "has_inputs": true,
    "template": {
      "url_or_bvid": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "url_or_bvid",
        "display_name": "url_or_bvid",
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
        "value": "str",
        "password": false,
        "options": [
          {
            "value": "str",
            "label": "str"
          },
          {
            "value": "list",
            "label": "list"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "output_subtitle": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output_subtitle",
        "display_name": "output_subtitle",
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
  item.label = t(`components.nodes.webCrawlers.BilibiliCrawler.${item.value}`)
  return item
})

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.webCrawlers.BilibiliCrawler.title')" :description="props.data.description"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="url_or_bvid" :name="t('components.nodes.webCrawlers.BilibiliCrawler.url_or_bvid')" required
            type="target" v-model:show="fieldsData.url_or_bvid.show">
            <a-input v-model:value="fieldsData.url_or_bvid.value" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_type" :name="t('components.nodes.webCrawlers.BilibiliCrawler.output_type')" required
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
          <BaseField id="output_title" :name="t('components.nodes.webCrawlers.BilibiliCrawler.output_title')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_subtitle" :name="t('components.nodes.webCrawlers.BilibiliCrawler.output_subtitle')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>