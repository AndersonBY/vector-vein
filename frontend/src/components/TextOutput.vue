<script setup>
import { computed } from 'vue'
import VueMarkdown from 'vue-markdown-render'

const props = defineProps({
  text: {
    type: String,
    default: '',
  },
  renderMarkdown: {
    type: Boolean,
    default: false,
  },
  wrapperClass: {
    type: [String, Array],
    default: [],
  },
  showCopy: {
    type: Boolean,
    default: true,
  },
})
const innerText = computed(() => {
  if (typeof props.text === 'string') {
    return props.text
  } else {
    return JSON.stringify(props.text)
  }
})
</script>

<template>
  <div :class="wrapperClass">
    <template v-if="renderMarkdown">
      <vue-markdown v-highlight :source="innerText" :options="{ html: true }" class="markdown-body custom-hljs" />
      <a-typography-paragraph v-if="showCopy" :copyable="{ text: innerText }">
      </a-typography-paragraph>
    </template>
    <a-typography-paragraph :copyable="showCopy ? false : { text: innerText }" v-else>
      {{ innerText }}
    </a-typography-paragraph>
  </div>
</template>