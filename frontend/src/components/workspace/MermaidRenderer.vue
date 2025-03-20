<script setup>
import { ref, onMounted, watch } from 'vue'
import { Download, Copy, Check } from '@icon-park/vue-next'
import { Flex, Tooltip, Button } from 'ant-design-vue'
import { saveAs } from 'file-saver'
import mermaid from "mermaid"

const props = defineProps({
  content: {
    type: String,
    required: true,
    default: '',
  },
  downloadTitle: {
    type: String,
    default: 'Download SVG',
  },
  id: {
    type: String,
    default: () => `mermaid-${Date.now()}-${Math.floor(Math.random() * 10000)}`
  }
})

mermaid.initialize({ startOnLoad: false, securityLevel: "loose" })
const mermaidRef = ref()
const content = ref(props.content)

const update = async () => {
  if (!content.value) {
    return
  }
  // 如果是Markdown代码格式的Mermaid，先用正则表达式提取出Mermaid代码，否则直接渲染可能有问题
  const mermaidCode = content.value.match(/```mermaid((.|\n)*?)```/)?.[1] || content.value
  // 渲染Mermaid
  try {
    const { svg } = await mermaid.render(props.id, mermaidCode)
    mermaidRef.value.innerHTML = svg
  } catch (error) {
    console.error('Mermaid rendering error:', error)
    mermaidRef.value.innerHTML = `<div style="color:red">Mermaid rendering error: ${error.message}</div>`
  }
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

const isCopied = ref(false)
const copyTip = ref('Copy Mermaid Code')
const copyMermaidCode = () => {
  const mermaidCode = content.value.match(/```mermaid((.|\n)*?)```/)?.[1] || content.value
  navigator.clipboard.writeText(mermaidCode)

  // 设置复制状态为真，并在1秒后恢复
  isCopied.value = true
  copyTip.value = 'Copied'
  setTimeout(() => {
    isCopied.value = false
    copyTip.value = 'Copy Mermaid Code'
  }, 1000)
}
</script>

<template>
  <Flex vertical>
    <div class="mermaid" ref="mermaidRef" style="width: 100%;">
    </div>
    <Flex gap="small">
      <Tooltip :title="downloadTitle">
        <Button @click="downloadMermaid" type="text">
          <template #icon>
            <Download />
          </template>
        </Button>
      </Tooltip>
      <Tooltip :title="copyTip">
        <Button @click="copyMermaidCode" type="text">
          <template #icon>
            <template v-if="isCopied">
              <Check />
            </template>
            <template v-else>
              <Copy />
            </template>
          </template>
        </Button>
      </Tooltip>
    </Flex>
  </Flex>
</template>