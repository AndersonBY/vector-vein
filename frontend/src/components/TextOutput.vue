<script setup>
import { ref, computed, onMounted, watch, nextTick, onBeforeUnmount, h, render } from 'vue'
import { Copy } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import VueMarkdown from 'vue-markdown-render'
import markdownItKatex from '@vscode/markdown-it-katex'
import MarkdownItGitHubAlerts from 'markdown-it-github-alerts'
import MarkdownItLinkAttributes from 'markdown-it-link-attributes'
import MermaidRenderer from '@/components/workspace/MermaidRenderer.vue'
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
  renderMermaid: {
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

const { t } = useI18n()

const innerText = computed(() => {
  if (typeof props.text === 'string') {
    const escapedText = escapeBrackets(escapeDollarNumber(props.text))
    return escapedText
  } else {
    let processedText = ''
    if (Array.isArray(props.text)) {
      processedText = props.text.map(item => {
        if (typeof item !== 'string') {
          try {
            return JSON.stringify(item)
          } catch (error) {
            return ''
          }
        }
        return item
      }).join('\n\n')
    } else {
      try {
        processedText = JSON.stringify(props.text)
      } catch (error) {
        processedText = ''
      }
    }
    try {
      return escapeBrackets(escapeDollarNumber(processedText))
    } catch (error) {
      return ''
    }
  }
})

const titles = {
  tip: t('common.TIP'),
  note: t('common.NOTE'),
  important: t('common.IMPORTANT'),
  warning: t('common.WARNING'),
  caution: t('common.CAUTION'),
}

const markdownitGitHubAlertsPlugin = (vueMarkdownItInstance) => {
  const md = vueMarkdownItInstance
  md.use(MarkdownItGitHubAlerts, {
    titles
  })
}

const markdownItLinkAttributesPlugin = (vueMarkdownItInstance) => {
  const md = vueMarkdownItInstance
  md.use(MarkdownItLinkAttributes, {
    attrs: {
      target: '_blank',
    }
  })
}

const plugins = [markdownItKatex, markdownitGitHubAlertsPlugin, markdownItLinkAttributesPlugin]

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
    blocks.forEach((block, index) => {
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

      const createCopyIcon = () => h(Copy, {
        theme: 'outline',
        size: '18',
        fill: '#fff',
        class: 'copy-icon',
        onClick: () => {
          const textToCopy = block.textContent.replace(/\n$/, '');
          navigator.clipboard.writeText(textToCopy).then(() => {
            render(h('span', { class: 'copied-text' }, 'Copied!'), copyContainer)
            setTimeout(() => {
              renderCopyIcon()
            }, 1000)
          }).catch(err => {
            console.error('Failed to copy text: ', err)
          })
        }
      })

      const renderCopyIcon = () => {
        render(createCopyIcon(), copyContainer)
      }

      renderCopyIcon()
    })
  }
}

const renderMermaidCodeBlock = () => {
  if (!markdownRef.value || !props.renderMermaid) return

  const codeBlocks = markdownRef.value.$el.querySelectorAll('pre code.language-mermaid')
  codeBlocks.forEach(block => {
    try {
      // 创建一个容器替换原始代码块
      const container = document.createElement('div')
      container.className = 'mermaid-container'

      // 获取父元素的父元素（pre的父元素）
      const preParent = block.parentNode.parentNode

      // 将容器插入到pre元素之前
      preParent.insertBefore(container, block.parentNode)

      // 渲染MermaidRenderer组件
      render(h(MermaidRenderer, {
        content: block.textContent,
        downloadTitle: t('components.workspace.mindmapRenderer.download_svg')
      }), container)

      // 隐藏原始pre元素
      block.parentNode.style.display = 'none'
    } catch (error) {
      console.error('Error rendering mermaid block:', error)
      // 如果渲染失败，保留原始代码块
      if (block.parentNode) {
        block.parentNode.style.display = ''
      }
      // 添加错误提示
      const errorDiv = document.createElement('div')
      errorDiv.className = 'mermaid-error'
      errorDiv.style.color = 'red'
      errorDiv.textContent = `Mermaid rendering error: ${error.message}`
      if (block.parentNode && block.parentNode.parentNode) {
        block.parentNode.parentNode.insertBefore(errorDiv, block.parentNode)
      }
    }
  })
}

onMounted(() => {
  nextTick(() => {
    highlightCodeBlocks()
    renderMermaidCodeBlock()
  })
})

watch(() => props.text, () => {
  nextTick(() => {
    highlightCodeBlocks()
    renderMermaidCodeBlock()
  })
})

onBeforeUnmount(() => {
  if (markdownRef.value) {
    // 清理代码块
    const codeBlocks = markdownRef.value.$el.querySelectorAll('.code-block')
    codeBlocks.forEach(block => {
      const copyContainer = block.querySelector('.copy-container')
      if (copyContainer) {
        render(null, copyContainer)
      }
      block.remove()
    })

    // 清理Mermaid容器
    const mermaidContainers = markdownRef.value.$el.querySelectorAll('.mermaid-container')
    mermaidContainers.forEach(container => {
      render(null, container)
      container.remove()
    })

    // 清理Mermaid错误信息
    const mermaidErrors = markdownRef.value.$el.querySelectorAll('.mermaid-error')
    mermaidErrors.forEach(error => {
      error.remove()
    })
  }
})
</script>

<template>
  <div :class="wrapperClass">
    <template v-if="renderMarkdown">
      <vue-markdown ref="markdownRef" :source="innerText" :options="{ html: true, linkify: true }" :plugins="plugins"
        class="markdown-body custom-hljs custom-scrollbar" :class="markdownBodyClass" />
      <a-typography-paragraph v-if="showCopy" :copyable="{ text: innerText }">
      </a-typography-paragraph>
    </template>
    <a-typography-paragraph :copyable="showCopy ? false : { text: innerText }" v-else>
      {{ innerText }}
    </a-typography-paragraph>
  </div>
</template>

<style>
.code-block .header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 10px;
  background-color: #f0f0f0;
}

.code-block .copy-container {
  cursor: pointer;
  display: flex;
  align-items: center;
}

.code-block .copy-icon {
  transition: opacity 0.3s;
  cursor: pointer;
}

.code-block .copy-icon:hover {
  opacity: 0.7;
}

.code-block .copied-text {
  font-size: 12px;
}

.mermaid-container {
  width: 100%;
  margin: 1rem 0;
  padding: 1rem;
}

.mermaid-error {
  width: 100%;
  margin: 0.5rem 0;
  padding: 0.5rem 1rem;
  background-color: #fff0f0;
  border-left: 3px solid #ff6b6b;
  border-radius: 2px;
  font-family: monospace;
  white-space: pre-wrap;
}
</style>