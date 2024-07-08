<script setup>
import { computed } from 'vue'
import VueMarkdown from 'vue-markdown-render'
import markdownItKatex from '@vscode/markdown-it-katex'
import 'katex/dist/katex.min.css'

const props = defineProps({
  text: {
    type: String,
    default: '',
  },
  renderMarkdown: {
    type: Boolean,
    default: true,
  },
  wrapperClass: {
    type: [String, Array],
    default: [],
  },
  markdownBodyClass: {
    type: [String, Array],
    default: [],
  },
  showCopy: {
    type: Boolean,
    default: true,
  },
})
const innerText = computed(() => {
  if (typeof props.text === 'string') {
    const escapedText = escapeBrackets(escapeDollarNumber(props.text))
    return escapedText
  } else {
    try {
      return escapeBrackets(escapeDollarNumber(JSON.stringify(props.text)))
    } catch (error) {
      return ''
    }
  }
})

const plugins = [markdownItKatex]

// Taken from https://github.com/Chanzhaoyu/chatgpt-web/blob/main/src/views/chat/components/Message/Text.vue
function escapeDollarNumber(text) {
  let escapedText = ''

  for (let i = 0; i < text.length; i += 1) {
    let char = text[i]
    const nextChar = text[i + 1] || ' '

    if (char === '$' && nextChar >= '0' && nextChar <= '9')
      char = '\\$'

    escapedText += char
  }

  return escapedText
}

function escapeBrackets(text) {
  const pattern = /(```[\s\S]*?```|`.*?`)|\\\[([\s\S]*?[^\\])\\\]|\\\((.*?)\\\)/g
  return text.replace(pattern, (match, codeBlock, squareBracket, roundBracket) => {
    if (codeBlock)
      return codeBlock
    else if (squareBracket)
      return `$$${squareBracket}$$`
    else if (roundBracket)
      return `$${roundBracket}$`
    return match
  })
}

const markdownBodyClass = computed(() => typeof props.markdownBodyClass === 'string' ? [props.markdownBodyClass] : props.markdownBodyClass)
</script>

<template>
  <div :class="wrapperClass">
    <template v-if="renderMarkdown">
      <vue-markdown v-highlight :source="innerText" :options="{ html: true }" :plugins="plugins"
        class="markdown-body custom-hljs custom-scrollbar" :class="markdownBodyClass" />
      <a-typography-paragraph v-if="showCopy" :copyable="{ text: innerText }">
      </a-typography-paragraph>
    </template>
    <a-typography-paragraph :copyable="showCopy ? false : { text: innerText }" v-else>
      {{ innerText }}
    </a-typography-paragraph>
  </div>
</template>