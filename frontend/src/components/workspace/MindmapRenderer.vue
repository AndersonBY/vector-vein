<script setup>
import { ref, onMounted, onUpdated, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download } from '@icon-park/vue-next'
import { Transformer } from 'markmap-lib'
import { Markmap, loadCSS, loadJS } from 'markmap-view/dist/index.esm'
import { saveAs } from 'file-saver'

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
const transformer = new Transformer()
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

</script>

<template>
  <a-flex vertical>
    <svg id="markmap" ref="svgRef" style="width: 100%; min-height: 50vh;" />
    <a-tooltip :title="t('components.workspace.mindmapRenderer.download_svg')">
      <a-button @click="downloadMindmap" type="text">
        <template #icon>
          <Download />
        </template>
      </a-button>
    </a-tooltip>
  </a-flex>
</template>