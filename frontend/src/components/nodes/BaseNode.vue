<script setup>
import { defineComponent } from 'vue'
import { DeleteOutlined } from '@ant-design/icons-vue'

defineComponent({
  name: 'BaseNode',
})
const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    required: false,
  },
})
const emit = defineEmits(['delete'])
</script>

<template>
  <div class="node">
    <div style="width: 100%;">
      <div class="title-container">
        <a-typography-title :level="3">
          {{ props.title }}
        </a-typography-title>
        <a-typography-title :level="3">
          <a-typography-link @click="emit('delete')">
            <DeleteOutlined />
          </a-typography-link>
        </a-typography-title>
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
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  border-bottom: 1px solid #e2e2e2;
  background: #f8f8f8;
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