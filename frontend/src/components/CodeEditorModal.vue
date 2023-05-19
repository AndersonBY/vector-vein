<script setup>
import { defineComponent, defineEmits, watch, ref, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { python } from '@codemirror/lang-python'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from "@codemirror/view"
import { Codemirror } from 'vue-codemirror'
import { CodeOutlined } from '@ant-design/icons-vue'

defineComponent({
  name: 'CodeEditorModal',
})

const props = defineProps({
  code: {
    type: String,
    required: true,
    default: '',
  },
  open: {
    type: Boolean,
    required: true,
    default: false,
  },
  language: {
    type: String,
    required: true,
    default: 'python',
  },
})

const { t } = useI18n()

const emit = defineEmits(['update:code', 'update:open'])
let innerCode = ref(props.code)
let innerOpen = ref(props.open)
const updateCode = (event) => {
  innerCode.value = event
  emit('update:code', innerCode.value)
}
const updateOpen = (newValue) => {
  innerOpen.value = newValue
  emit('update:open', innerOpen.value)
}
watch(() => props.code, (newValue) => {
  innerCode.value = newValue
})
watch(() => props.open, (newValue) => {
  innerOpen.value = newValue
})

const FontSizeTheme = EditorView.theme({
  ".cm-content": {
    fontFamily: "Cascadia Code, Consolas, Monaco, Menlo, Ubuntu Mono, Liberation Mono, DejaVu Sans Mono, Courier New, monospace",
    fontSize: '24px',
  },
})

const extensions = [python(), oneDark, FontSizeTheme]
const languageSettings = {
  python: {
    extensions: [python(), oneDark, FontSizeTheme],
    tabSize: 4,
  }
}
const view = shallowRef()
const handleReady = (payload) => {
  view.value = payload.view
}
</script>

<template>
  <a-modal :open="innerOpen" width="80vw" @ok="updateOpen(false)" @cancel="updateOpen(false)">
    <template #title>
      <CodeOutlined />
      {{ t('components.codeEditorModal.title') }}
    </template>
    <codemirror class="editor" v-model="innerCode" :placeholder="t('components.codeEditorModal.please_enter_code')"
      :style="{ height: '80vh', minHeight: '400px' }" :autofocus="true" :indent-with-tab="true"
      :tab-size="languageSettings[props.language].tabSize" :extensions="languageSettings[props.language].extensions"
      @ready="handleReady" @change="updateCode($event)" />
  </a-modal>
</template>