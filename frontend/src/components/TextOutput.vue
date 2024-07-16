<script setup>
import { ref, computed, onMounted, onUpdated, nextTick, onBeforeUnmount, h, render } from 'vue'
import { Typography } from 'ant-design-vue'
import VueMarkdown from 'vue-markdown-render'
import markdownItKatex from '@vscode/markdown-it-katex'
import 'katex/dist/katex.min.css'
import hljs from 'highlight.js'
import 'highlight.js/styles/monokai-sublime.css'

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
const markdownRef = ref(null)

const highlightCodeBlocks = () => {
  if (markdownRef.value) {
    const blocks = markdownRef.value.$el.querySelectorAll('pre code')
    blocks.forEach((block) => {
      if (block.parentNode.classList.contains('code-block')) {
        return
      }

      hljs.highlightElement(block)
      block.classList.add('custom-scrollbar', 'hljs')

      const wrapper = document.createElement('div')
      const header = document.createElement('div')
      const lang = document.createElement('span')
      const copyContainer = document.createElement('div')

      wrapper.className = 'code-block'
      header.className = 'header'
      lang.className = 'language'
      copyContainer.className = 'copy-container'

      const blockClassList = Array.from(block.classList)
      const language = blockClassList.find(c => c.startsWith('language-'))
      lang.textContent = language ? language.split('-')[1] : ''

      header.appendChild(lang)
      header.appendChild(copyContainer)
      wrapper.appendChild(header)
      block.parentNode.insertBefore(wrapper, block)
      wrapper.appendChild(block)

      const copyButton = h(Typography.Paragraph, {
        copyable: { text: block.textContent },
      })
      render(copyButton, copyContainer)
    })
  }
}

onMounted(() => {
  nextTick(highlightCodeBlocks)
})

onUpdated(() => {
  nextTick(highlightCodeBlocks)
})

onBeforeUnmount(() => {
  let blocks = document.querySelectorAll('.code-block')
  blocks.forEach(block => {
    block.remove()
  })
})
</script>

<template>
  <div :class="wrapperClass">
    <template v-if="renderMarkdown">
      <vue-markdown ref="markdownRef" :source="innerText" :options="{ html: true }" :plugins="plugins"
        class="markdown-body custom-hljs custom-scrollbar" :class="markdownBodyClass" />
      <a-typography-paragraph v-if="showCopy" :copyable="{ text: innerText }">
      </a-typography-paragraph>
    </template>
    <a-typography-paragraph :copyable="showCopy ? false : { text: innerText }" v-else>
      {{ innerText }}
    </a-typography-paragraph>
  </div>
</template>