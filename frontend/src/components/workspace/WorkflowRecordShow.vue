<script setup>
import { ref } from "vue"
import VueMarkdown from 'vue-markdown-render'
import { Dot } from '@icon-park/vue-next'
import AudioPlayer from "@/components/workspace/AudioPlayer.vue"
import MindmapRenderer from "@/components/workspace/MindmapRenderer.vue"
import MermaidRenderer from "@/components/workspace/MermaidRenderer.vue"
import EchartsRenderer from "@/components/workspace/EchartsRenderer.vue"
import TableRenderer from "@/components/workspace/TableRenderer.vue"
import TextOutput from "@/components/TextOutput.vue"
import { getUIDesignFromWorkflow } from '@/utils/workflow'

const props = defineProps({
  workflowData: {
    type: Object,
    required: true
  }
})

const uiDesign = getUIDesignFromWorkflow(props.workflowData)
const outputNodes = ref(uiDesign.outputNodes)
</script>

<template>
  <div>
    <template v-for="(node) in outputNodes" :key="`node-${node.id}`">
      <template v-if="node.type == 'Text'">
        <a-col :span="24">
          <a-typography-title :level="5" class="text-output-title">
            <Dot fill="#28c5e5" />
            {{ node.data.template.output_title.value }}
          </a-typography-title>
          <TextOutput :key="node.id" :text="node.data.template.text.value"
            :renderMarkdown="node.data.template.render_markdown.value" />
        </a-col>
      </template>

      <template v-else-if="node.type == 'Audio'">
        <a-col :span="24">
          <AudioPlayer :key="node.id" :audios="[node.data.template.audio_url.value]"
            :isMidi="node.data.template.is_midi?.value" />
        </a-col>
      </template>

      <template v-else-if="node.type == 'Mindmap'">
        <a-col :span="24">
          <MindmapRenderer :key="node.id" :content="node.data.template.content.value"
            style="width: 100%;min-height: 50vh;" />
        </a-col>
      </template>

      <template v-else-if="node.type == 'Mermaid'">
        <a-col :span="24">
          <MermaidRenderer :key="node.id" :content="node.data.template.content.value"
            style="width: 100%;min-height: 50vh;" />
        </a-col>
      </template>

      <template v-else-if="node.type == 'Echarts'">
        <a-col :span="24">
          <EchartsRenderer :key="node.id" :option="node.data.template.option.value"
            style="width: 100%;min-height: 50vh;" />
        </a-col>
      </template>

      <template v-else-if="node.type == 'Table'">
        <a-col :span="24">
          <TableRenderer :key="node.id" :data="node.data.template.output.value"
            :bordered="node.data.template.bordered.value" style="width: 100%;" />
        </a-col>
      </template>

      <template v-else-if="node.type == 'Html'">
        <a-col :span="24">
          <iframe class="html-iframe" :src="node.data.template.output.value" style="width: 100%;min-height: 50vh;" />
        </a-col>
      </template>

      <template v-else>
        <a-col :span="24">
          <div v-if="node.field_type == 'typography-paragraph'">
            <vue-markdown v-highlight :source="node.value" :options="{ html: true }"
              class="markdown-body custom-hljs ui-special-item" />
          </div>
        </a-col>
      </template>
    </template>
  </div>
</template>

<style scoped>
.html-iframe {
  border: 2px solid #dedede;
  border-radius: 10px;
  width: 100%;
  min-height: 80vh;
}

.text-output-title {
  color: #005b79;
}
</style>