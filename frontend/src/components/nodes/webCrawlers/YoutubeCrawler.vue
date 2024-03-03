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
      "get_comments": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": false,
        "password": false,
        "name": "get_comments",
        "display_name": "get_comments",
        "type": "bool",
        "clear_after_run": true,
        "list": false,
        "field_type": "checkbox"
      },
      "comments_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "text_only",
        "password": false,
        "options": [
          {
            "value": "text_only",
            "label": "text_only"
          },
          {
            "value": "detailed",
            "label": "detailed"
          },
        ],
        "name": "comments_type",
        "display_name": "comments_type",
        "type": "bool",
        "clear_after_run": true,
        "list": false,
        "field_type": "radio"
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
      "output_comments": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output_comments",
        "display_name": "output_comments",
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

if (!fieldsData.value.get_comments) {
  fieldsData.value.get_comments = {
    "required": true,
    "placeholder": "",
    "show": false,
    "multiline": false,
    "value": false,
    "password": false,
    "name": "get_comments",
    "display_name": "get_comments",
    "type": "bool",
    "clear_after_run": true,
    "list": false,
    "field_type": "checkbox"
  }
}
if (!fieldsData.value.comments_type) {
  fieldsData.value.comments_type = {
    "required": true,
    "placeholder": "",
    "show": false,
    "multiline": false,
    "value": "text_only",
    "password": false,
    "options": [
      {
        "value": "text_only",
        "label": "text_only"
      },
      {
        "value": "detailed",
        "label": "detailed"
      },
    ],
    "name": "comments_type",
    "display_name": "comments_type",
    "type": "bool",
    "clear_after_run": true,
    "list": false,
    "field_type": "radio"
  }
}

fieldsData.value.comments_type.options = fieldsData.value.comments_type.options.map(item => {
  item.label = t(`components.nodes.webCrawlers.YoutubeCrawler.comments_type_${item.value}`)
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
        <a-col :span="24">
          <BaseField id="get_comments" :name="t('components.nodes.webCrawlers.YoutubeCrawler.get_comments')" required
            type="target" v-model:show="fieldsData.get_comments.show">
            <template #inline>
              <a-checkbox v-model:checked="fieldsData.get_comments.value">
              </a-checkbox>
            </template>
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="comments_type" :name="t('components.nodes.webCrawlers.YoutubeCrawler.comments_type')" required
            type="target" v-model:show="fieldsData.comments_type.show">
            <a-radio-group option-type="button" v-model:value="fieldsData.comments_type.value"
              :options="fieldsData.comments_type.options" />
          </BaseField>
        </a-col>
      </a-row>
    </template>

    <template #output>
      <a-row type="flex" style="width: 100%;">
        <a-col :span="24">
          <BaseField id="output_title" :name="t('components.nodes.webCrawlers.YoutubeCrawler.output_title')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_subtitle" :name="t('components.nodes.webCrawlers.YoutubeCrawler.output_subtitle')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_comments" :name="t('components.nodes.webCrawlers.YoutubeCrawler.output_comments')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>