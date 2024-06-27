<script setup>
import { FileSuccess, Close } from '@icon-park/vue-next'

const props = defineProps({
  removable: {
    type: Boolean,
    default: true,
  },
})
const attachments = defineModel()
const removeAttachment = (file) => {
  attachments.value.splice(attachments.value.indexOf(file), 1)
}
</script>

<template>
  <a-flex gap="small" wrap="wrap" class="chat-attachments-list-area">
    <div class="attachment-item" v-for="attachment in attachments">
      <a-flex gap="small" align="center" style="width: 100%;">
        <FileSuccess />
        <a-tooltip :title="attachment">
          <a-typography-text :ellipsis="true" :content="attachment.slice(0, 48)">
          </a-typography-text>
        </a-tooltip>
      </a-flex>
      <a-button class="remove-item-button" type="text" size="small" shape="circle" @click="removeAttachment(attachment)"
        v-if="removable">
        <template #icon>
          <Close />
        </template>
      </a-button>
    </div>
  </a-flex>
</template>

<style scoped>
.attachment-item {
  background-color: #f2f2f2;
  border-radius: 10px;
  padding: 16px;
  position: relative;
  margin-bottom: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  max-width: 150px;
}

.attachment-item>.remove-item-button {
  position: absolute;
  top: 0px;
  right: 0px;
  background-color: transparent;
  border: none;
}

.attachment-item>.remove-item-button:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.attachment-item .a-typography-text {
  color: #333;
  margin-right: auto;
}
</style>