<script setup>
import { computed, nextTick, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme } from 'ant-design-vue'
import { Handle, Position, VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { AddOne, ReduceOne, FullScreenOne } from '@/icons'
import { getWorkflowPreview } from '@/utils/workflowPreview'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const props = defineProps({
  workflow: { type: Object, default: () => ({}) },
  height: { type: String, default: '500px' },
})
const { t, te } = useI18n()
const { token } = theme.useToken()
const canvasStyle = computed(() => ({
  height: props.height,
  '--preview-background': token.value.colorBgContainer,
  '--preview-text': token.value.colorText,
  '--preview-border': token.value.colorBorder,
  '--preview-edge': token.value.colorTextSecondary,
  '--preview-primary': token.value.colorPrimary,
}))
const flowId = `workflow-preview-${useId()}`
const { fitView, zoomIn, zoomOut } = useVueFlow(flowId)
const preview = computed(() => getWorkflowPreview(props.workflow, t, te))
const fit = () => fitView({ padding: 0.2, maxZoom: 1 })
watch(preview, async () => {
  await nextTick()
  fit()
}, { flush: 'post' })
</script>

<template>
  <div class="canvas-preview" :style="canvasStyle">
    <VueFlow v-if="preview.nodes.length" :id="flowId" :nodes="preview.nodes" :edges="preview.edges"
      :nodes-draggable="false" :nodes-connectable="false" :elements-selectable="false" :edges-updatable="false"
      :nodes-focusable="false" :edges-focusable="false" :delete-key-code="null" :selection-key-code="false"
      :multi-selection-key-code="null" :connect-on-click="false" :pan-on-drag="true" :zoom-on-scroll="true"
      :zoom-on-pinch="true" :min-zoom="0.1" :max-zoom="2" fit-view-on-init @nodes-initialized="fit">
      <template #node-preview="{ data }">
        <div class="preview-node" :class="{ 'preview-node-ignored': data.ignored }">
          <div class="preview-node-heading">
            <strong>{{ data.title }}</strong>
            <span v-if="data.ignored" class="preview-ignored">{{ t('workspace.canvasPreview.ignored') }}</span>
          </div>
          <div v-if="data.inputs.length || data.outputs.length" class="preview-ports">
            <div class="preview-inputs">
              <div v-for="port in data.inputs" :key="port.id" class="preview-port" :title="port.label">
                <Handle :id="port.id || undefined" type="target" :position="Position.Left" :connectable="false"
                  :connectable-start="false" :connectable-end="false" />
                <span>{{ port.label }}</span>
              </div>
            </div>
            <div class="preview-outputs">
              <div v-for="port in data.outputs" :key="port.id" class="preview-port" :title="port.label">
                <Handle :id="port.id || undefined" type="source" :position="Position.Right" :connectable="false"
                  :connectable-start="false" :connectable-end="false" />
                <span>{{ port.label }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
      <Background pattern-color="var(--preview-edge, #666)" :gap="20" :size="0.5" />
      <div class="preview-controls nopan">
        <a-button :aria-label="t('workspace.canvasPreview.zoom_in')" :title="t('workspace.canvasPreview.zoom_in')" @click="zoomIn()">
          <template #icon><AddOne /></template>
        </a-button>
        <a-button :aria-label="t('workspace.canvasPreview.zoom_out')" :title="t('workspace.canvasPreview.zoom_out')" @click="zoomOut()">
          <template #icon><ReduceOne /></template>
        </a-button>
        <a-button :aria-label="t('workspace.canvasPreview.fit_view')" :title="t('workspace.canvasPreview.fit_view')" @click="fit">
          <template #icon><FullScreenOne /></template>
        </a-button>
      </div>
    </VueFlow>
    <div v-else class="preview-empty">{{ t('workspace.canvasPreview.empty') }}</div>
  </div>
</template>

<style scoped>
.canvas-preview {
  position: relative;
  width: 100%;
  min-height: 160px;
  overflow: hidden;
  border: 1px solid var(--preview-border, #d9d9d9);
  border-radius: 8px;
  background: var(--preview-background, #fff);
  color: var(--preview-text, #222);
}
.preview-node {
  width: 240px;
  padding: 12px;
  border: 1px solid var(--preview-primary, #28c5e5);
  border-radius: 8px;
  background: var(--preview-background, #fff);
  font-size: 13px;
}
.preview-node-ignored { opacity: 0.55; border-style: dashed; }
.preview-node-heading { display: flex; flex-direction: column; gap: 4px; overflow-wrap: anywhere; }
.preview-ignored { font-size: 11px; }
.preview-ports { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; margin-top: 12px; }
.preview-port { position: relative; height: 26px; display: flex; align-items: center; }
.preview-port span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-outputs .preview-port { justify-content: flex-end; }
.preview-inputs .vue-flow__handle { left: -16px; }
.preview-outputs .vue-flow__handle { right: -16px; }
.preview-port .vue-flow__handle { width: 7px; height: 7px; background: var(--preview-primary, #28c5e5); pointer-events: none; }
.preview-controls { position: absolute; left: 12px; bottom: 12px; z-index: 5; display: flex; gap: 4px; }
.preview-controls :deep(.ant-btn) {
  background: var(--preview-background, #fff);
  color: var(--preview-text, #222);
  border-color: var(--preview-border, #d9d9d9);
}
.preview-empty { height: 100%; display: grid; place-items: center; }
</style>
