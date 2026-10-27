<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowReactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme } from 'ant-design-vue'
import { FileSuccess, Close, Picture, LoadingFour } from '@/icons'
import { getAttachmentInfo, loadAttachmentImage } from '@/utils/chatAttachments'

const props = defineProps({ removable: { type: Boolean, default: true } })
const attachments = defineModel({ default: () => [] })
const { t } = useI18n()
const { token } = theme.useToken()
const items = computed(() => {
  const values = Array.isArray(attachments.value) ? attachments.value : typeof attachments.value === 'string' ? [attachments.value] : []
  return values.map((value, index) => ({ ...getAttachmentInfo(value, index), index }))
})
const thumbnails = shallowReactive(new Map())
const opening = ref('')
const previewError = ref('')
const preview = reactive({ path: '', name: '', src: '', visible: false })
const label = item => item.name || t('workspace.chatSpace.attachment_unnamed')
let previewVersion = 0
let disposed = false
let stop

const closePreview = () => {
  previewVersion++
  opening.value = ''
  Object.assign(preview, { path: '', name: '', src: '', visible: false })
}
const openImage = async item => {
  const version = ++previewVersion
  opening.value = item.path
  previewError.value = ''
  const current = () => !disposed && version === previewVersion && items.value.some(value => value.path === item.path)
  try {
    const src = await loadAttachmentImage(item, false, current)
    if (!current()) return
    if (src) Object.assign(preview, { path: item.path, name: label(item), src, visible: true })
    else previewError.value = item.path
  } finally {
    if (version === previewVersion) opening.value = ''
  }
}
const previewVisibleChange = visible => { if (!visible) closePreview() }
const previewFailed = () => {
  previewError.value = preview.path
  closePreview()
}
const thumbnailFailed = path => {
  const state = thumbnails.get(path)
  if (state) Object.assign(state, { src: '', loading: false, failed: true })
}
const removeAttachment = index => {
  if (!props.removable) return
  const values = Array.isArray(attachments.value) ? attachments.value : [attachments.value]
  attachments.value = values.filter((_, i) => i !== index)
}
onMounted(() => {
  stop = watch(items, values => {
    const images = values.filter(item => item.image)
    const paths = new Set(images.map(item => item.path))
    for (const path of thumbnails.keys()) if (!paths.has(path)) thumbnails.delete(path)
    if (preview.path && !paths.has(preview.path) || opening.value && !paths.has(opening.value)) closePreview()
    for (const item of images) {
      if (thumbnails.has(item.path)) continue
      const state = reactive({ src: '', loading: true, failed: false })
      thumbnails.set(item.path, state)
      const current = () => !disposed && thumbnails.get(item.path) === state
      loadAttachmentImage(item, true, current).then(src => {
        if (current()) Object.assign(state, { src: src || '', loading: false, failed: !src })
      })
    }
  }, { immediate: true })
})
onBeforeUnmount(() => {
  disposed = true
  stop?.()
  thumbnails.clear()
  closePreview()
})
</script>

<template>
  <a-flex gap="small" wrap="wrap" class="chat-attachments-list-area" :style="{
    '--attachment-background': token.colorBgContainer,
    '--attachment-border': token.colorBorderSecondary,
    '--attachment-text': token.colorText,
    '--attachment-secondary': token.colorTextSecondary,
  }">
    <div v-for="item in items" :key="item.key" class="chat-attachment"
      :class="{ 'chat-attachment-image': item.image, 'chat-attachment-removable': removable }">
      <template v-if="item.image">
        <button type="button" class="attachment-thumbnail" :aria-label="t('workspace.chatSpace.attachment_preview', { name: label(item) })"
          :disabled="!thumbnails.get(item.path)?.src || opening === item.path" @click="openImage(item)">
          <img v-if="thumbnails.get(item.path)?.src" :src="thumbnails.get(item.path).src" :alt="label(item)"
            loading="lazy" @error="thumbnailFailed(item.path)" />
          <Picture v-else :size="28" />
          <span v-if="opening === item.path" class="attachment-opening" role="status" :aria-label="t('workspace.chatSpace.attachment_loading')">
            <LoadingFour :spin="true" :size="20" />
          </span>
        </button>
        <span class="attachment-name" :title="label(item)">{{ label(item) }}</span>
        <span v-if="thumbnails.get(item.path)?.failed || previewError === item.path" class="attachment-unavailable" role="status">
          {{ t('workspace.chatSpace.attachment_unavailable') }}
        </span>
      </template>
      <template v-else>
        <FileSuccess :size="18" class="attachment-file-icon" />
        <span class="attachment-name" :title="label(item)">{{ label(item) }}</span>
      </template>
      <a-button v-if="removable" class="attachment-remove" type="text" size="small" shape="circle"
        :aria-label="t('workspace.chatSpace.attachment_remove', { name: label(item) })" @click.stop="removeAttachment(item.index)">
        <template #icon><Close /></template>
      </a-button>
    </div>
    <a-image v-if="preview.src" :src="preview.src" :alt="preview.name" :wrapper-style="{ display: 'none' }"
      :preview="{ visible: preview.visible, onVisibleChange: previewVisibleChange }" @error="previewFailed" />
  </a-flex>
</template>

<style scoped>
.chat-attachment { position: relative; display: flex; align-items: center; gap: 8px; min-width: 0; max-width: min(240px, 100%); padding: 8px 12px; border: 1px solid var(--attachment-border); border-radius: 6px; background: var(--attachment-background); color: var(--attachment-text); }
.chat-attachment-removable:not(.chat-attachment-image) { padding-right: 32px; }
.chat-attachment-image { flex-direction: column; width: 114px; padding: 8px; gap: 6px; }
.attachment-thumbnail { position: relative; display: grid; place-items: center; width: 96px; height: 80px; padding: 0; border: 0; border-radius: 4px; background: transparent; color: var(--attachment-secondary); cursor: pointer; }
.attachment-thumbnail:disabled { cursor: default; }
.attachment-thumbnail:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
.attachment-thumbnail img { display: block; width: 96px; height: 80px; object-fit: cover; border-radius: 4px; }
.attachment-name { display: block; min-width: 0; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-attachment-image .attachment-name, .attachment-unavailable { font-size: 12px; }
.attachment-unavailable { color: var(--attachment-secondary); }
.attachment-file-icon { flex-shrink: 0; }
.attachment-opening { position: absolute; inset: 0; display: grid; place-items: center; background: var(--attachment-background); opacity: 0.85; }
.attachment-remove { position: absolute; top: 2px; right: 2px; background: var(--attachment-background); }
</style>
