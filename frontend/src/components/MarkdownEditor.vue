<script setup>
import { ref } from "vue"
import { useI18n } from 'vue-i18n'
import VueMarkdown from 'vue-markdown-render'

const props = defineProps({
  placeholder: {
    type: String,
    default: ''
  }
})

const { t } = useI18n()
const markdown = defineModel()
const preview = ref(false)
</script>

<template>
  <div>
    <a-form-item-rest>
      <a-checkbox v-model:checked="preview">
        {{ t('common.preview') }}
      </a-checkbox>
    </a-form-item-rest>
    <a-textarea v-model:value="markdown" :autoSize="{ minRows: 3, maxRows: 10 }" :placeholder="props.placeholder"
      v-show="!preview" />
    <VueMarkdown v-highlight v-model:source="markdown" class="custom-scrollbar markdown-body custom-hljs"
      v-show="preview" />
  </div>
</template>
