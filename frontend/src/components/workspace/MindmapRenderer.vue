<script setup>
import { ref, onMounted, onUpdated, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { DownPicture, MindMapping } from '@icon-park/vue-next'
import { Transformer } from 'markmap-lib/no-plugins'
import { pluginFrontmatter } from 'markmap-lib/plugins'
import { Markmap, loadCSS, loadJS } from 'markmap-view'
import { saveAs } from 'file-saver'
import { Topic, RootTopic, Workbook } from 'xmind-generator'

const { t } = useI18n()

const props = defineProps({
  content: {
    type: String,
    required: true,
    default: '',
  },
})

const svgRef = ref()
const content = ref(props.content)
const rootRef = ref()
let mm
const transformer = new Transformer([pluginFrontmatter])
const update = () => {
  const { root, features } = transformer.transform(content.value)
  const { styles, scripts } = transformer.getUsedAssets(features)
  if (styles) loadCSS(styles);
  if (scripts) loadJS(scripts, { getMarkmap: () => window.markmap })
  rootRef.value = root
  mm.setData(root)
  mm.fit()
}

onMounted(() => {
  mm = Markmap.create(svgRef.value)
  update()
})
onUpdated(update)
watch(() => props.content, () => {
  content.value = props.content
})

const downloadMindmap = () => {
  const svgEl = document.querySelector('#markmap')
  const svgData = new XMLSerializer().serializeToString(svgEl)
  const blob = new Blob([svgData], { type: 'image/svg+xml' })
  saveAs(blob, 'mindmap.svg')
}

const decodeHTMLEntities = (text) => {
  const textarea = document.createElement('textarea');
  textarea.innerHTML = text;
  return textarea.getHTML()
}

const exportToXmind = async () => {
  const rootNode = rootRef.value
  const buildTopic = (node) => {
    const topic = Topic(decodeHTMLEntities(node.content))
    if (node.children && node.children.length > 0) {
      topic.children(node.children.map(child => buildTopic(child)))
    }
    return topic
  }
  const rootTopic = RootTopic(decodeHTMLEntities(rootNode.content)).children(rootNode.children.map(child => buildTopic(child)))
  const workbook = Workbook(rootTopic)

  const arrayBuffer = await workbook.archive()

  const blob = new Blob([arrayBuffer], { type: 'application/vnd.xmind.workbook' })
  saveAs(blob, 'mindmap.xmind')
}

</script>

<template>
  <a-flex vertical>
    <svg id="markmap" ref="svgRef" style="width: 100%; min-height: 50vh;" />
    <a-space>
      <a-tooltip :title="t('components.workspace.mindmapRenderer.download_svg')">
        <a-button @click="downloadMindmap" type="text">
          <template #icon>
            <DownPicture />
          </template>
        </a-button>
      </a-tooltip>
      <a-tooltip :title="t('components.workspace.mindmapRenderer.download_xmind')">
        <a-button @click="exportToXmind" type="text">
          <template #icon>
            <MindMapping />
          </template>
        </a-button>
      </a-tooltip>
    </a-space>
  </a-flex>
</template>