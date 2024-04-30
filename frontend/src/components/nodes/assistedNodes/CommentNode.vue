<script setup>
import { ref } from 'vue'
import { Delete } from '@icon-park/vue-next'
import { useNodeMessagesStore } from '@/stores/nodeMessages'
import { NodeResizer } from '@vue-flow/node-resizer'
import { createTemplateData } from './CommentNode'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
})

const useNodeMessages = useNodeMessagesStore()

const pushMessage = (action, data) => {
  useNodeMessages.push({
    action,
    data,
    nodeId: props.id,
  })
}

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})
</script>

<template>
  <div class="comment-node">
    <NodeResizer min-width="100" min-height="30" />
    <div style="width: 100%;">
      <div class="title-container">
        <a-typography-title :level="5" editable v-model:content="fieldsData.comment.value" class="comment-text" />
        <a-typography-link @click="pushMessage('delete')" class="delete-button">
          <Delete />
        </a-typography-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.comment-node {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 100%;
}

.comment-node .title-container {
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px;
  padding-top: 20px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
}

.comment-node .title-container .comment-text {
  color: #545454;
  width: 100%;
}

.comment-node .title-container .hint-popover {
  font-size: 14px;
  color: #a0a0a0;
}

.comment-node .description-container {
  padding: 10px;
  color: #b8b8b8;
}

.comment-node .main-container {
  margin-bottom: 10px;
}

.comment-node .output-container {
  padding: 10px 0;
  display: flex;
}

.comment-node .output-container:empty {
  padding: 0;
}


.comment-node .output-container span {
  float: right;
  margin-right: 10px;
  color: white;
  font-size: 18px;
}

.comment-node .delete-button {
  opacity: 0;
}

.comment-node:hover .delete-button {
  opacity: 1;
}
</style>

<style>
.comment-node .vue-flow__resize-control {
  opacity: 0;
}

.comment-node:hover .vue-flow__resize-control {
  opacity: 1;
}

.vue-flow__resize-control {
  position: absolute;
}

.vue-flow__resize-control.left,
.vue-flow__resize-control.right {
  cursor: ew-resize;
}

.vue-flow__resize-control.top,
.vue-flow__resize-control.bottom {
  cursor: ns-resize;
}

.vue-flow__resize-control.top.left,
.vue-flow__resize-control.bottom.right {
  cursor: nwse-resize;
}

.vue-flow__resize-control.bottom.left,
.vue-flow__resize-control.top.right {
  cursor: nesw-resize;
}

.vue-flow__resize-control.handle {
  width: 5px;
  height: 5px;
  border: 1px solid #fff;
  border-radius: 1px;
  background-color: #3367d9;
  transform: translate(-50%, -50%);
}

.vue-flow__resize-control.handle.left {
  left: 0;
  top: 50%;
}

.vue-flow__resize-control.handle.right {
  left: 100%;
  top: 50%;
}

.vue-flow__resize-control.handle.top {
  left: 50%;
  top: 0;
}

.vue-flow__resize-control.handle.bottom {
  left: 50%;
  top: 100%;
}

.vue-flow__resize-control.handle.top.left,
.vue-flow__resize-control.handle.bottom.left {
  left: 0;
}

.vue-flow__resize-control.handle.top.right,
.vue-flow__resize-control.handle.bottom.right {
  left: 100%;
}

.vue-flow__resize-control.line {
  border-color: #3367d9;
  border-width: 0;
  border-style: solid;
}

.vue-flow__resize-control.line.left,
.vue-flow__resize-control.line.right {
  width: 1px;
  transform: translate(-50%);
  top: 0;
  height: 100%;
}

.vue-flow__resize-control.line.left {
  left: 0;
  border-left-width: 5px;
}

.vue-flow__resize-control.line.right {
  left: 100%;
  border-right-width: 5px;
}

.vue-flow__resize-control.line.top,
.vue-flow__resize-control.line.bottom {
  height: 1px;
  transform: translateY(-50%);
  left: 0;
  width: 100%;
}

.vue-flow__resize-control.line.top {
  top: 0;
  border-top-width: 5px;
}

.vue-flow__resize-control.line.bottom {
  border-bottom-width: 5px;
  top: 100%;
}
</style>