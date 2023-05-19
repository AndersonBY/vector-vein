<script setup>
import { defineComponent, ref } from "vue"
import { Editor, rootCtx, defaultValueCtx } from "@milkdown/core"
import { nord } from "@milkdown/theme-nord"
import { Milkdown, useEditor } from "@milkdown/vue"
import { commonmark } from "@milkdown/preset-commonmark"
import { listener, listenerCtx } from '@milkdown/plugin-listener'

defineComponent({
  name: "MilkdownEditor",
})

const props = defineProps({
  markdown: {
    type: String,
    required: true,
    default: '',
  },
})

const emit = defineEmits(['update:markdown'])
let innerMarkdown = ref(props.markdown)

const updateMarkdown = (markdown) => {
  innerMarkdown.value = markdown
  emit('update:markdown', innerMarkdown.value)
}

useEditor((root) => {
  return Editor.make()
    .config(nord)
    .config((ctx) => {
      ctx.set(rootCtx, root)
      ctx.set(defaultValueCtx, innerMarkdown.value)

      const listener = ctx.get(listenerCtx)
      listener.markdownUpdated((ctx, markdown, prevMarkdown) => {
        if (markdown !== prevMarkdown) {
          updateMarkdown(markdown)
        }
      })
    })
    .use(commonmark)
    .use(listener)
})
</script>

<template>
  <Milkdown class="milkdown-editor" />
</template>

<style scoped>
.milkdown-editor {
  border-radius: 4px;
  border-width: 1px;
  border-style: solid;
  border-color: #d9d9d9;
}
</style>