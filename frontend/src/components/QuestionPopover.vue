<template>
  <a-popover :overlayClassName="(overlayClassName).join(' ')">
    <template #content>
      <template v-for="content in props.contents" :key="content">
        <a-typography-paragraph v-if="typeof content == 'string'">
          {{ content }}
        </a-typography-paragraph>
        <a-typography-paragraph v-else-if="content.type == 'link'">
          <a-typography-link :href="content.url" target="_blank">
            {{ content.text }}
          </a-typography-link>
        </a-typography-paragraph>
        <div v-else>
          <img v-if="content.type == 'image'" :src="content.url" />
        </div>
      </template>
    </template>
    <question-circle-outlined :style="{ margin: '0 2px' }" />
  </a-popover>
</template>
  
<script setup>
import { defineComponent, ref } from "vue"
import { QuestionCircleOutlined } from '@ant-design/icons-vue'

defineComponent({
  name: "QuestionPopover",
})

const props = defineProps({
  contents: {
    type: Array,
    required: true,
  },
  fixedWidth: {
    type: Boolean,
    default: true,
  },
})
const overlayClassName = ref(['question-popover'])
if (props.fixedWidth) overlayClassName.value.push('question-popover-fixed-width')
</script>
  
<style>
.question-popover-fixed-width.ant-popover {
  max-width: 300px;
}

.question-popover-auto-width.ant-popover {
  max-width: 100%;
}

.question-popover .ant-popover-inner-content .ant-typography:last-child {
  margin-bottom: 0;
}
</style>