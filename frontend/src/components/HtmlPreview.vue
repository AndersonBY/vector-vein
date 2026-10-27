<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, theme } from 'ant-design-vue'
import { FullScreenOne, OffScreenOne } from '@/icons'
import { buildPreviewHtml, previewSourceUrl } from '@/utils/htmlPreview'

const props = defineProps({ url: { type: String, default: '' }, title: { type: String, default: '' }, pending: Boolean })
const { t } = useI18n()
const { token } = theme.useToken()
const title = computed(() => props.title || t('workspace.htmlPreview.title'))
const container = ref(null)
const frame = ref(null)
const frameUrl = ref('')
const loading = ref(false)
const failed = ref(false)
const fullscreen = ref(false)
let generation = 0
let controller
let timeout
let objectUrl = ''
let disposed = false

const release = () => {
  clearTimeout(timeout)
  controller?.abort()
  controller = null
  frameUrl.value = ''
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = ''
}
const fail = () => {
  release()
  failed.value = true
  loading.value = false
}
const load = async () => {
  const version = ++generation
  release()
  failed.value = false
  loading.value = props.pending
  if (props.pending) return
  if (!props.url) return
  const source = previewSourceUrl(props.url)
  if (!source) { fail(); return }
  loading.value = true
  const request = new AbortController()
  controller = request
  const current = () => !disposed && version === generation && !request.signal.aborted
  timeout = setTimeout(() => { if (current()) fail() }, 30000)
  try {
    const response = await fetch(source, { signal: request.signal, credentials: 'omit' })
    if (!current()) return
    if (!response.ok) throw new Error('HTML unavailable')
    const content = await response.text()
    if (!current()) return
    const html = buildPreviewHtml(content, response.url || source)
    objectUrl = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
    frameUrl.value = objectUrl
  } catch {
    if (current()) fail()
  }
}
const frameLoaded = event => {
  if (!frameUrl.value || event.target !== frame.value) return
  clearTimeout(timeout)
  loading.value = false
}
const frameFailed = event => { if (frameUrl.value && event.target === frame.value) fail() }
const fullscreenChanged = () => { fullscreen.value = Boolean(container.value && document.fullscreenElement === container.value) }
const toggleFullscreen = async () => {
  try {
    if (fullscreen.value) await document.exitFullscreen()
    else await container.value.requestFullscreen()
  } catch { message.error(t('workspace.htmlPreview.fullscreen_failed')) }
}
watch(() => [props.url, props.pending], load, { immediate: true })
onMounted(() => document.addEventListener('fullscreenchange', fullscreenChanged))
onBeforeUnmount(() => {
  disposed = true
  generation++
  release()
  document.removeEventListener('fullscreenchange', fullscreenChanged)
  if (container.value && document.fullscreenElement === container.value) void document.exitFullscreen().catch(() => {})
})
</script>

<template>
  <section v-if="url || pending" ref="container" class="html-preview" :aria-label="title" :aria-busy="loading" :style="{
    '--preview-background': token.colorBgContainer, '--preview-border': token.colorBorderSecondary,
    '--preview-text': token.colorText, '--preview-secondary': token.colorTextSecondary,
  }">
    <header class="html-preview-toolbar">
      <span class="html-preview-title">{{ title }}</span>
      <a-tooltip :title="t(fullscreen ? 'workspace.htmlPreview.restore' : 'workspace.htmlPreview.expand')">
        <a-button size="small" type="text" :aria-label="t(fullscreen ? 'workspace.htmlPreview.restore' : 'workspace.htmlPreview.expand')" @click="toggleFullscreen">
          <template #icon><OffScreenOne v-if="fullscreen" /><FullScreenOne v-else /></template>
        </a-button>
      </a-tooltip>
    </header>
    <div class="html-preview-content">
      <div v-if="loading" class="html-preview-loading" role="status" :aria-label="t('workspace.htmlPreview.loading')"><a-spin /></div>
      <div v-if="failed" class="html-preview-error" role="status">
        <span>{{ t('workspace.htmlPreview.load_failed') }}</span>
        <a-button size="small" @click="load">{{ t('workspace.htmlPreview.retry') }}</a-button>
      </div>
      <iframe v-else-if="frameUrl" :key="frameUrl" ref="frame" :src="frameUrl" :title="title" sandbox="allow-scripts"
        referrerpolicy="no-referrer" class="html-preview-frame" @load="frameLoaded" @error="frameFailed" />
    </div>
  </section>
</template>

<style scoped>
.html-preview { display: flex; flex-direction: column; width: 100%; height: 65vh; min-height: 320px; border: 1px solid var(--preview-border); border-radius: 6px; overflow: hidden; background: var(--preview-background); color: var(--preview-text); }
.html-preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 12px; border-bottom: 1px solid var(--preview-border); flex-shrink: 0; }
.html-preview-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.html-preview-content { position: relative; flex: 1; min-height: 0; }
.html-preview-frame { display: block; width: 100%; height: 100%; border: 0; background: white; }
.html-preview-loading { position: absolute; inset: 0; display: grid; place-items: center; background: var(--preview-background); z-index: 1; }
.html-preview-error { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; height: 100%; color: var(--preview-secondary); }
.html-preview:fullscreen { height: 100vh; min-height: 0; border: 0; border-radius: 0; }
</style>
