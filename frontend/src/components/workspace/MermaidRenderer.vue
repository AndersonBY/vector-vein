<script setup>
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download } from '@icon-park/vue-next'
import mermaid from "mermaid"
import { saveAs } from 'file-saver'

const { t } = useI18n()

const props = defineProps({
  content: {
    type: String,
    required: true,
    default: '',
  },
})

mermaid.mermaidAPI.initialize({ startOnLoad: false, securityLevel: "loose" })
const mermaidRef = ref()
const content = ref(props.content)
const update = async () => {
  if (!content.value) {
    return
  }
  // 如果是Markdown代码格式的Mermaid，先用正则表达式提取出Mermaid代码，否则直接渲染可能有问题
  const mermaidCode = content.value.match(/```mermaid((.|\n)*?)```/)?.[1] || content.value
  // 渲染Mermaid
  const { svg } = await mermaid.render('graphDiv', mermaidCode)
  mermaidRef.value.innerHTML = svg
}

onMounted(() => {
  update()
})

watch(() => props.content, () => {
  content.value = props.content
  update()
})

const downloadMermaid = () => {
  const svgData = new XMLSerializer().serializeToString(mermaidRef.value)
  const blob = new Blob([svgData], { type: 'image/svg+xml' })
  saveAs(blob, 'mermaid.svg')
}

</script>

<template>
  <a-flex vertical>
    <div class="mermaid" ref="mermaidRef" style="width: 100%; min-height: 50vh;">
    </div>
    <a-tooltip :title="t('components.workspace.mindmapRenderer.download_svg')">
      <a-button @click="downloadMermaid" type="text">
        <template #icon>
          <Download />
        </template>
      </a-button>
    </a-tooltip>
  </a-flex>
</template>