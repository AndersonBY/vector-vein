<script setup>
import { defineComponent, ref, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { MilkdownProvider } from "@milkdown/vue"
import MilkdownEditor from '@/components/MilkdownEditor.vue'

defineComponent({
  name: "MarkdownEditor",
})

const props = defineProps({
  markdown: {
    type: String,
    required: true,
    default: '',
  },
})

const { t } = useI18n()

const emit = defineEmits(['update:markdown'])
let innerMarkdown = ref(props.markdown)

watch(() => innerMarkdown.value, (markdown) => {
  emit('update:markdown', innerMarkdown.value)
})

const editMethod = ref('markdown')
</script>

<template>
  <div>
    <a-form-item-rest>
      <a-radio-group style="margin-bottom: 15px;" v-model:value="editMethod">
        <a-radio-button value="rawText">
          {{ t('components.markdownEditor.raw_text') }}
        </a-radio-button>
        <a-radio-button value="markdown">
          {{ t('components.markdownEditor.markdown_text') }}
        </a-radio-button>
      </a-radio-group>
    </a-form-item-rest>

    <MilkdownProvider v-if="editMethod == 'markdown'">
      <MilkdownEditor v-model:markdown="innerMarkdown" />
    </MilkdownProvider>
    <a-textarea v-model:value="innerMarkdown" :auto-size="{ minRows: 5 }" :show-count="true" v-else>
    </a-textarea>
  </div>
</template>
