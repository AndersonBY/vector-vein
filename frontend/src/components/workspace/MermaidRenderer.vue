<script setup>
import { defineComponent, ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import mermaid from "mermaid"
import { saveAs } from 'file-saver'

defineComponent({
  name: 'MindmapRenderer',
})

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
  // 如果是Markdown代码格式的Mermaid，先用正则表达式提取出Mermaid代码，否则直接渲染
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
  <a-row>
    <a-col :span="24">
      <div class="mermaid" ref="mermaidRef" style="width: 100%; min-height: 50vh;">
      </div>
    </a-col>
    <a-col :span="24">
      <a-button @click="downloadMermaid" type="primary">
        {{ t('components.workspace.mindmapRenderer.download_svg') }}
      </a-button>
    </a-col>
  </a-row>
</template>