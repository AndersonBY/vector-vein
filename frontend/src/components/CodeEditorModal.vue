<script setup>
import { defineComponent, watch, ref, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { json } from '@codemirror/lang-json'
import { python } from '@codemirror/lang-python'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from "@codemirror/view"
import { Codemirror } from 'vue-codemirror'
import { FileCode } from '@icon-park/vue-next'

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
    required: false,
    default: 'python',
  },
})

const { t } = useI18n()

const emit = defineEmits(['update:code', 'update:open', 'save'])
let innerCode = ref(props.code)
let innerOpen = ref(props.open)
const updateCode = (event) => {
  innerCode.value = event
  emit('update:code', innerCode.value)
}
const updateOpen = (newValue, isOk) => {
  innerOpen.value = newValue
  emit('update:open', innerOpen.value)
  if (isOk) {
    emit('save', innerCode.value)
  }
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

const languageSettings = {
  python: {
    extensions: [python(), oneDark, FontSizeTheme],
    tabSize: 4,
  },
  json: {
    extensions: [json(), oneDark, FontSizeTheme],
    tabSize: 2,
  }
}
const view = shallowRef()
const handleReady = (payload) => {
  view.value = payload.view
}
</script>

<template>
  <a-modal :open="innerOpen" width="80vw" @ok="updateOpen(false, true)" @cancel="updateOpen(false, false)">
    <template #title>
      <a-space>
        <FileCode />
        {{ t('components.codeEditorModal.title') }}

        <a-typography-text :copyable="{ text: props.code }">
          <template #copyableTooltip="{ copied }">
            <span v-if="!copied" key="copy-tooltip">
              {{ t('components.codeEditorModal.copy_code') }}
            </span>
            <span v-else key="copied-tooltip">
              {{ t('components.codeEditorModal.copy_success') }}
            </span>
          </template>
        </a-typography-text>
      </a-space>
    </template>
    <codemirror class="code-editor" v-model="innerCode" :placeholder="t('components.codeEditorModal.please_enter_code')"
      :style="{ height: '80vh', minHeight: '400px' }" :autofocus="true" :indent-with-tab="true"
      :tab-size="languageSettings[props.language].tabSize" :extensions="languageSettings[props.language].extensions"
      @ready="handleReady" @change="updateCode($event)" />
  </a-modal>
</template>

<style>
.code-editor .cm-scroller::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.code-editor .cm-scroller::-webkit-scrollbar-thumb {
  background: #CCCCCC;
  border-radius: 6px;
}

.code-editor .cm-scroller::-webkit-scrollbar-track {
  background: transparent;
}
</style>