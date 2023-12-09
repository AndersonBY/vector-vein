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
    "task_name": "media_processing.gpt_vision",
    "has_inputs": true,
    "template": {
      "text_prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "text_prompt",
        "display_name": "text_prompt",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "images_or_urls": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "images",
        "password": false,
        "options": [
          {
            "value": "images",
            "label": "images"
          },
          {
            "value": "urls",
            "label": "urls"
          },
        ],
        "name": "images_or_urls",
        "display_name": "images_or_urls",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "radio"
      },
      "images": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": true,
        "value": [],
        "password": false,
        "name": "images",
        "display_name": "images",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "file",
        "support_file_types": ".jpg, .jpeg, .png, .webp"
      },
      "urls": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "urls",
        "display_name": "urls",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "detail_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "auto",
        "password": false,
        "options": [
          {
            "value": "auto",
            "label": "auto"
          },
          {
            "value": "low",
            "label": "low"
          },
          {
            "value": "high",
            "label": "high"
          },
        ],
        "name": "detail_type",
        "display_name": "detail_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "radio"
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
  }
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
fieldsData.value.detail_type.options = fieldsData.value.detail_type.options.map(item => {
  item.label = t(`components.nodes.mediaProcessing.GptVision.detail_type_${item.value}`)
  return item
})
fieldsData.value.images_or_urls.options = fieldsData.value.images_or_urls.options.map(item => {
  item.label = t(`components.nodes.mediaProcessing.GptVision.${item.value}`)
  return item
})

const typeChange = () => {
  if (fieldsData.value.images_or_urls.value == 'images') {
    fieldsData.value.urls.show = false
  } else {
    fieldsData.value.images.show = false
  }
}
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.mediaProcessing.GptVision.title')"
    :description="props.data.description" documentLink="https://vectorvein.com/help/docs/media-processing#h2-4">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="text_prompt" :name="t('components.nodes.mediaProcessing.GptVision.text_prompt')" required
            type="target" v-model:show="fieldsData.text_prompt.show">
            <a-textarea class="field-content" v-model:value="fieldsData.text_prompt.value" :autoSize="true"
              :showCount="true" :placeholder="fieldsData.text_prompt.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="images_or_urls" :name="t('components.nodes.mediaProcessing.GptVision.images_or_urls')" required
            type="target" v-model:show="fieldsData.images_or_urls.show">
            <a-radio-group option-type="button" v-model:value="fieldsData.images_or_urls.value"
              :options="fieldsData.images_or_urls.options" @change="typeChange" />
          </BaseField>
        </a-col>

        <a-col :span="24" v-show="fieldsData.images_or_urls.value == 'images'">
          <BaseField id="images" :name="t('components.nodes.mediaProcessing.GptVision.images')" required type="target"
            v-model:show="fieldsData.images.show">
          </BaseField>
        </a-col>

        <a-col :span="24" v-show="fieldsData.images_or_urls.value == 'urls'">
          <BaseField id="urls" :name="t('components.nodes.mediaProcessing.GptVision.urls')" required type="target"
            v-model:show="fieldsData.urls.show">
            <a-input class="field-content" v-model:value="fieldsData.urls.value"
              :placeholder="fieldsData.urls.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="detail_type" :name="t('components.nodes.mediaProcessing.GptVision.detail_type')" required
            type="target" v-model:show="fieldsData.detail_type.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.detail_type.value"
              :options="fieldsData.detail_type.options" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.mediaProcessing.GptVision.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>