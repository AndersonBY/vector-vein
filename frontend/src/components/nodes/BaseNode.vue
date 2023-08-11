<script setup>
import { Delete, Copy } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { useNodeMessagesStore } from '@/stores/nodeMessages'
import QuestionPopover from '@/components/QuestionPopover.vue'

const props = defineProps({
  nodeId: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    required: false,
  },
  documentLink: {
    type: String,
    required: false,
    default: '',
  },
})

const useNodeMessages = useNodeMessagesStore()

const pushMessage = (action, data) => {
  useNodeMessages.push({
    action,
    data,
    nodeId: props.nodeId,
  })
}

const { t } = useI18n()
</script>

<template>
  <div class="node">
    <div style="width: 100%;">
      <div class="title-container">
        <a-typography-title :level="3" style="flex-grow: 1;">
          {{ props.title }}
          <QuestionPopover
            :contents="[{ type: 'link', text: t('components.nodes.baseNode.document_link'), url: props.documentLink }]"
            v-if="props.documentLink.length > 0" class="hint-popover" />
        </a-typography-title>
        <a-tooltip color="blue" :title="t('components.nodes.baseNode.clone_node')">
          <a-typography-link @click="pushMessage('clone')">
            <Copy />
          </a-typography-link>
        </a-tooltip>
        <a-tooltip color="red" :title="t('components.nodes.baseNode.delete_node')">
          <a-typography-link @click="pushMessage('delete')">
            <Delete />
          </a-typography-link>
        </a-tooltip>
      </div>

      <div class="description-container">
        <a-typography-paragraph>
          {{ props.description }}
        </a-typography-paragraph>
      </div>

      <div class="main-container">
        <slot name="main"></slot>
      </div>

      <div class="output-container">
        <slot name="output"></slot>
      </div>
    </div>
  </div>
</template>

<style>
.node {
  border: 1px solid #777;
  border-radius: 10px;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  min-width: 150px;
  max-width: 400px;
}

.node .title-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px;
  padding-top: 20px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  border-bottom: 1px solid #e2e2e2;
  background: #f8f8f8;
}

.node .title-container .hint-popover {
  font-size: 14px;
  color: #a0a0a0;
}

.node .description-container {
  padding: 10px;
  color: #b8b8b8;
}

.node .main-container {
  margin-bottom: 10px;
}

.node .output-container {
  padding: 10px 0;
  display: flex;
}

.node .output-container:empty {
  padding: 0;
}

.node .output-container span {
  float: right;
  margin-right: 10px;
  color: white;
  font-size: 18px;
}
</style>