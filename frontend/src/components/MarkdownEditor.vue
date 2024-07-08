<script setup>
import { ref } from "vue"
import { useI18n } from 'vue-i18n'
import TextOutput from "./TextOutput.vue"

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
    <TextOutput v-show="preview" :text="markdown" :showCopy="false" />
  </div>
</template>
