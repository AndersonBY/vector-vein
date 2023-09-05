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
  <template v-if="renderMarkdown">
    <vue-markdown v-highlight :source="innerText" class="markdown-body custom-hljs" />
    <a-typography-paragraph :copyable="{ text: innerText }">
    </a-typography-paragraph>
  </template>
  <a-typography-paragraph :copyable="{ text: innerText }" v-else>
    {{ innerText }}
  </a-typography-paragraph>
</template>