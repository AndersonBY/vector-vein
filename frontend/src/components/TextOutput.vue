<script setup>
import { ref, computed, onMounted, onBeforeUpdate, onUpdated, onBeforeUnmount, h, render } from 'vue'
import { Copy, Check } from '@/icons'
import { streamingMarkdownPlugin } from '@/utils/streamingMarkdown'
import { useI18n } from 'vue-i18n'
import VueMarkdown from 'vue-markdown-render'
import markdownItKatexModule from '@vscode/markdown-it-katex'

const markdownItKatex = markdownItKatexModule.default || markdownItKatexModule
import MarkdownItGitHubAlerts from 'markdown-it-github-alerts'
import MarkdownItLinkAttributes from 'markdown-it-link-attributes'
import MermaidRenderer from '@/components/workspace/MermaidRenderer.vue'
import 'katex/dist/katex.min.css'
import hljs from 'highlight.js'
import 'highlight.js/styles/monokai-sublime.css'

const props = defineProps({
  text: {
    type: [String, Array, Object],
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

function rawText(value) {
  if (typeof value === 'string') return value
  try {
    return Array.isArray(value) ? value.map(rawText).join('\n\n') : JSON.stringify(value) || ''
  } catch {
    return ''
  }
}
const innerText = computed(() => rawText(props.text))

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

const plugins = [markdownItKatex, md => streamingMarkdownPlugin(md, { copyLabel: t('components.copyButton.click_to_copy') }), markdownitGitHubAlertsPlugin, markdownItLinkAttributesPlugin]

const markdownBodyClass = computed(() => typeof props.markdownBodyClass === 'string' ? [props.markdownBodyClass] : props.markdownBodyClass)
const markdownRef = ref(null)

const mounts = new Map()
const timers = new Set()
const copyButtons = new Set()
let alive = true

function setCodeVisible(wrapper, visible) {
  wrapper.style.background = visible ? '' : 'transparent'
  wrapper.querySelector('pre').style.display = visible ? '' : 'none'
  wrapper.querySelector('.header').style.display = visible ? '' : 'none'
}

function prepareUpdate() {
  for (const timer of timers) clearTimeout(timer)
  timers.clear()
  for (const button of copyButtons) render(null, button)
  copyButtons.clear()
  for (const { wrapper, container } of mounts.values()) {
    container.remove()
    setCodeVisible(wrapper, true)
  }
}

function cleanup() {
  prepareUpdate()
  for (const { container } of mounts.values()) render(null, container)
  mounts.clear()
}

function renderCopyIcon(button, copied = false) {
  const label = t(copied ? 'components.copyButton.copy_success' : 'components.copyButton.click_to_copy')
  button.setAttribute('aria-label', label)
  button.setAttribute('title', label)
  render(h(copied ? Check : Copy, { class: 'copy-icon', size: '18' }), button)
  copyButtons.add(button)
}

function enhanceMarkdown() {
  const root = markdownRef.value?.$el
  if (!alive || !root?.querySelectorAll) { cleanup(); return }
  root.querySelectorAll('.copy-container').forEach(button => renderCopyIcon(button))
  root.querySelectorAll('pre code').forEach(block => {
    if (!block.dataset.highlighted && !block.classList.contains('language-mermaid')) hljs.highlightElement(block)
    block.classList.add('custom-scrollbar', 'hljs')
  })
  const used = new Set()
  if (props.renderMermaid) root.querySelectorAll('.code-block[data-mermaid="true"]').forEach((wrapper, index) => {
    const key = `${index}:${wrapper.dataset.code}`
    used.add(key)
    let mounted = mounts.get(key)
    if (mounted) {
      mounted.wrapper = wrapper
      wrapper.appendChild(mounted.container)
      if (mounted.rendered) setCodeVisible(wrapper, false)
      return
    }
    const container = document.createElement('div')
    container.className = 'mermaid-container'
    wrapper.appendChild(container)
    mounted = { wrapper, container, rendered: false }
    mounts.set(key, mounted)
    render(h(MermaidRenderer, {
      content: decodeURIComponent(wrapper.dataset.code),
      downloadTitle: t('components.workspace.mindmapRenderer.download_svg'),
      onRendered: () => {
        mounted.rendered = true
        setCodeVisible(mounted.wrapper, false)
      },
    }), container)
  })
  for (const [key, { container }] of mounts) {
    if (used.has(key)) continue
    render(null, container)
    container.remove()
    mounts.delete(key)
  }
}

async function copyCode(event) {
  const button = event.target.closest?.('.copy-container')
  const wrapper = button?.closest('.code-block')
  if (!wrapper) return
  try {
    await navigator.clipboard.writeText(decodeURIComponent(wrapper.dataset.code))
    if (!alive || !button.isConnected) return
    renderCopyIcon(button, true)
    const timer = setTimeout(() => {
      timers.delete(timer)
      renderCopyIcon(button)
    }, 1000)
    timers.add(timer)
  } catch (error) {
    console.error('Failed to copy text:', error)
  }
}

onMounted(enhanceMarkdown)
onBeforeUpdate(prepareUpdate)
onUpdated(enhanceMarkdown)
onBeforeUnmount(() => { alive = false; cleanup() })
</script>

<template>
  <div :class="wrapperClass" @click="copyCode">
    <template v-if="renderMarkdown">
      <vue-markdown ref="markdownRef" :source="innerText" :options="{ html: true, linkify: true }" :plugins="plugins"
        class="markdown-body custom-hljs custom-scrollbar" :class="markdownBodyClass" />
      <a-typography-paragraph v-if="showCopy" :copyable="{ text: innerText }">
      </a-typography-paragraph>
    </template>
    <a-typography-paragraph :copyable="showCopy ? { text: innerText } : false" v-else>
      {{ innerText }}
    </a-typography-paragraph>
  </div>
</template>

<style>
.markdown-body .code-block {
  margin: 1em 0;
  overflow: hidden;
  border-radius: 4px;
  background: #23241f;
}

.markdown-body .code-block .header {
  background-color: #343541;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #d9d9e3;
  padding: 8px 16px;
}

.code-block .language {
  font-size: 12px;
  line-height: 1;
}

.code-block .copy-container {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  padding: 0;
  border: 0;
  background: transparent;
}

.code-block .copy-icon {
  transition: opacity 0.3s;
}

.code-block .copy-icon:hover {
  opacity: 0.7;
}

.markdown-body .code-block pre,
.markdown-body .code-block code {
  margin: 0;
  padding: 0;
  border-radius: 0;
}

.markdown-body .code-block code.hljs {
  display: block;
  overflow-x: auto;
  padding: 1em;
  background: #23241f;
  color: #f8f8f2;
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