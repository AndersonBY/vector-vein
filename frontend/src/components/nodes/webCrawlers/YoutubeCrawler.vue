<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  templateData: {
    "description": "description",
    "task_name": "web_crawlers.youtube_crawler",
    "has_inputs": true,
    "template": {
      "url_or_video_id": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "url_or_video_id",
        "display_name": "url_or_video_id",
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

const { t } = useI18n()

const fieldsData = ref(props.data.template)
fieldsData.value.output_type.options = fieldsData.value.output_type.options.map(item => {
  item.label = t(`components.nodes.webCrawlers.YoutubeCrawler.${item.value}`)
  return item
})
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.webCrawlers.YoutubeCrawler.title')"
    :description="props.data.description" documentLink="https://vectorvein.com/help/docs/web-crawlers#h2-8">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="url_or_video_id" :name="t('components.nodes.webCrawlers.YoutubeCrawler.url_or_video_id')"
            required type="target" v-model:show="fieldsData.url_or_video_id.show">
            <a-input v-model:value="fieldsData.url_or_video_id.value" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_type" :name="t('components.nodes.webCrawlers.YoutubeCrawler.output_type')" required
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
          <BaseField id="output_title" :name="t('components.nodes.webCrawlers.YoutubeCrawler.output_title')" type="source"
            nameOnly>
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_subtitle" :name="t('components.nodes.webCrawlers.YoutubeCrawler.output_subtitle')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>