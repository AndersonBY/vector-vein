<script setup>
import { useI18n } from 'vue-i18n'
import { Delete } from '@icon-park/vue-next'
import MarkdownEditor from '@/components/MarkdownEditor.vue'

const { t } = useI18n()

const value = defineModel()

const props = defineProps({
  placeholder: {
    type: String,
    required: false,
    default: '',
  },
})

const emit = defineEmits(['change', 'delete'])

</script>

<template>
  <a-flex align="center" class="draggable-text-container">
    <MarkdownEditor class="markdown-editor" v-model="value" @change="emit('change')" />
    <a-tooltip :title="t('common.delete')">
      <a-button class="delete-button" type="text" @click="emit('delete')">
        <template #icon>
          <Delete style="flex-grow: 0;" />
        </template>
      </a-button>
    </a-tooltip>
  </a-flex>
</template>

<style scoped>
.markdown-editor {
  flex-grow: 1;
}

.draggable-text-container {
  margin-bottom: 24px;
  width: 100%;
}

.draggable-text-container .delete-button {
  opacity: 0;
  width: 0;
  transition: opacity 0.3s ease, width 0.3s ease;
}

.draggable-text-container:hover .delete-button {
  opacity: 1;
  width: 32px;
  margin-left: 8px;
}
</style>